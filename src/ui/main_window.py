import json
import time

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QLabel, QTabWidget,
    QStatusBar, QMessageBox, QSpinBox, QCheckBox,
)
from PyQt6.QtCore import QTimer, QSettings

from src.serial_worker import SerialWorker
from src.protocol_parser import ProtocolParser, ProtocolConfig
from src.data_store import DataStore
from src.ui.console_widget import ConsoleWidget
from src.ui.graph_widget import RealtimeGraphWidget
from src.ui.analysis_widget import AnalysisWidget
from src.ui.settings_dialog import SettingsDialog

_BAUD_RATES = [
    "9600", "19200", "38400", "57600",
    "115200", "230400", "250000", "460800", "921600",
]


def _format_bytes(n: float) -> str:
    if n < 1024:
        return f"{n:.0f} B"
    for unit in ("KB", "MB"):
        n /= 1024
        if n < 1024:
            return f"{n:.1f} {unit}"
    return f"{n / 1024:.1f} GB"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Serial Monitor")
        self.resize(820, 600)

        self._worker = SerialWorker()
        self._parser = ProtocolParser()
        self._store  = DataStore()
        self._config = ProtocolConfig()
        self._connected = False
        self._reconnect_port = ""
        self._reconnect_baud = 115200
        self._reconnecting = False

        self._reconnect_timer = QTimer()
        self._reconnect_timer.timeout.connect(self._try_reconnect)

        # Buffers for rate-limited display updates
        self._pending_lines: list[str] = []
        self._pending_samples: list[tuple[float, list, list[str]]] = []

        # Receive statistics
        self._rx_total = 0
        self._rx_window = 0
        self._rx_window_t = time.monotonic()

        self._settings = QSettings()
        self._last_port = ""

        self._build_ui()
        self._connect_signals()
        self._load_settings()

        # Port scan timer
        self._port_timer = QTimer()
        self._port_timer.timeout.connect(self._refresh_ports)
        self._port_timer.start(2000)
        self._refresh_ports()

        # Display update timer
        self._display_timer = QTimer()
        self._display_timer.timeout.connect(self._flush_pending)
        self._display_timer.start(self._interval_spin.value())

        # Receive-rate display timer
        self._rx_timer = QTimer()
        self._rx_timer.timeout.connect(self._update_rx_label)
        self._rx_timer.start(1000)

    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ---- Toolbar row 1: connection ----
        row1 = QHBoxLayout()

        row1.addWidget(QLabel("ポート:"))
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(100)
        row1.addWidget(self._port_combo)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(28)
        refresh_btn.clicked.connect(self._refresh_ports)
        row1.addWidget(refresh_btn)

        row1.addWidget(QLabel("ボーレート:"))
        self._baud_combo = QComboBox()
        self._baud_combo.addItems(_BAUD_RATES)
        self._baud_combo.setCurrentText("115200")
        row1.addWidget(self._baud_combo)

        self._conn_btn = QPushButton("接続")
        self._conn_btn.setCheckable(True)
        self._conn_btn.setMinimumWidth(70)
        self._conn_btn.clicked.connect(self._toggle_connection)
        row1.addWidget(self._conn_btn)

        row1.addSpacing(8)

        proto_btn = QPushButton("プロトコル設定")
        proto_btn.clicked.connect(self._open_settings)
        row1.addWidget(proto_btn)

        row1.addStretch()

        self._status_label = QLabel("未接続")
        self._status_label.setStyleSheet("color: gray;")
        row1.addWidget(self._status_label)

        root.addLayout(row1)

        # ---- Toolbar row 2: display settings ----
        row2 = QHBoxLayout()

        row2.addWidget(QLabel("更新周期:"))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(10, 5000)
        self._interval_spin.setValue(50)
        self._interval_spin.setSuffix(" ms")
        self._interval_spin.setToolTip(
            "UIの更新間隔 (ms)\n"
            "小さい値: リアルタイム性向上 / CPU負荷増\n"
            "大きい値: 高速データでも安定表示 / CPU負荷減"
        )
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        row2.addWidget(self._interval_spin)

        self._raw_cb = QCheckBox("生データ")
        self._raw_cb.setToolTip(
            "受信のたびに即時描画します。\n"
            "高レートのデータでは CPU 負荷が増えることがあります。"
        )
        self._raw_cb.stateChanged.connect(self._on_raw_mode_changed)
        row2.addWidget(self._raw_cb)

        row2.addStretch()

        root.addLayout(row2)

        # ---- Tabs ----
        self._tabs = QTabWidget()

        self._console = ConsoleWidget()
        self._tabs.addTab(self._console, "コンソール")

        self._graph = RealtimeGraphWidget()
        self._tabs.addTab(self._graph, "リアルタイムグラフ")

        self._analysis = AnalysisWidget(self._store)
        self._tabs.addTab(self._analysis, "解析")

        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs)

        self.setStatusBar(QStatusBar())
        self._rx_label = QLabel("受信: 0 B  |  0 B/s")
        self._rx_label.setStyleSheet("color: gray;")
        self._rx_label.setToolTip("受信した総バイト数 / 直近1秒あたりの受信レート")
        self.statusBar().addPermanentWidget(self._rx_label)

    def _connect_signals(self):
        self._worker.data_received.connect(self._on_raw_data)
        self._worker.error_occurred.connect(self._on_serial_error)
        self._worker.disconnected.connect(self._on_disconnected)

        self._parser.text_line_received.connect(self._on_text_line)
        self._parser.structured_received.connect(self._on_structured)

        self._console.send_requested.connect(self._on_send)
        self._analysis.data_clear_requested.connect(self._on_data_clear)

    # ------------------------------------------------------------------
    def _refresh_ports(self):
        current = self._port_combo.currentText()
        ports = SerialWorker.list_ports()
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        self._port_combo.addItems(ports)
        if current in ports:
            self._port_combo.setCurrentText(current)
        elif self._last_port in ports:
            # Select the port used last time when it appears
            self._port_combo.setCurrentText(self._last_port)
        self._port_combo.blockSignals(False)

    def _toggle_connection(self, checked: bool):
        if checked:
            port = self._port_combo.currentText()
            baud = int(self._baud_combo.currentText())
            if not port:
                QMessageBox.warning(self, "エラー", "ポートを選択してください")
                self._conn_btn.setChecked(False)
                return
            ok = self._worker.connect(port, baud)
            if ok:
                self._reconnect_port = port
                self._reconnect_baud = baud
                self._connected = True
                self._conn_btn.setText("切断")
                self._status_label.setText(f"接続中: {port} @ {baud}")
                self._status_label.setStyleSheet("color: #81C784;")
                self._store.reset()
                self._graph.clear()
                self._parser.reset()
                self._pending_lines.clear()
                self._pending_samples.clear()
                self._reset_rx_stats()
                self._save_settings()
            else:
                self._conn_btn.setChecked(False)
        else:
            # User manually disconnected — disable auto-reconnect
            self._reconnect_timer.stop()
            self._reconnect_port = ""
            self._disconnect()

    def _disconnect(self):
        self._worker.disconnect()
        self._connected = False
        self._conn_btn.setChecked(False)
        self._conn_btn.setText("接続")
        self._status_label.setText("未接続")
        self._status_label.setStyleSheet("color: gray;")

    def _try_reconnect(self):
        self._reconnecting = True
        ok = self._worker.connect(self._reconnect_port, self._reconnect_baud)
        self._reconnecting = False
        if ok:
            self._reconnect_timer.stop()
            self._connected = True
            self._conn_btn.setChecked(True)
            self._conn_btn.setText("切断")
            self._status_label.setText(f"再接続: {self._reconnect_port} @ {self._reconnect_baud}")
            self._status_label.setStyleSheet("color: #81C784;")
            self._parser.reset_buffer()
            self._pending_lines.clear()
            self._pending_samples.clear()

    def _open_settings(self):
        dlg = SettingsDialog(self._config, self)
        if dlg.exec():
            self._config = dlg.get_config()
            self._parser.set_config(self._config)
            names = self._channel_names_from_config()
            if names:
                self._graph.set_channels(names)
            self._store.reset()
            self._graph.clear()
            self._pending_lines.clear()
            self._pending_samples.clear()
            self._save_settings()

    def _channel_names_from_config(self) -> list[str]:
        if self._config.mode == "binary":
            return [f.name for f in self._config.binary_fields if f.graph and f.name]
        return self._config.channels

    def _on_interval_changed(self, ms: int):
        self._display_timer.setInterval(ms)

    def _on_raw_mode_changed(self, state: int):
        raw = state == 2
        self._interval_spin.setEnabled(not raw)

    # ------------------------------------------------------------------
    # Data reception (called from QThread via signal — safe to buffer here)
    def _on_raw_data(self, data: bytes):
        self._rx_total += len(data)
        self._rx_window += len(data)
        self._parser.feed(data)

    def _on_text_line(self, line: str):
        if self._raw_cb.isChecked():
            self._console.append_line(line)
        else:
            self._pending_lines.append(line)

    def _on_structured(self, timestamp: float, values: list, names: list):
        if not names:
            names = self._channel_names_from_config()
        if not names:
            names = [f"ch{i + 1}" for i in range(len(values))]
        names = (names + [f"ch{i + 1}" for i in range(len(names), len(values))])[:len(values)]
        self._store.add_sample(timestamp, values, names)
        if self._raw_cb.isChecked():
            self._graph.add_sample(timestamp, values, names)
            self._graph.refresh_curves()
        else:
            self._pending_samples.append((timestamp, values, names))

    # Flush buffers to UI at the configured display rate
    def _flush_pending(self):
        if self._pending_lines:
            self._console.append_lines(self._pending_lines)
            self._pending_lines = []

        if self._pending_samples:
            for timestamp, values, names in self._pending_samples:
                self._graph.add_sample(timestamp, values, names)
            self._pending_samples.clear()
            self._graph.refresh_curves()  # 1フラッシュにつき1回だけ描画

    def _on_data_clear(self):
        self._store.reset()
        self._graph.clear()
        self._parser.reset()
        self._pending_lines.clear()
        self._pending_samples.clear()
        self._analysis.refresh()

    # ------------------------------------------------------------------
    def _on_serial_error(self, msg: str):
        if self._reconnecting:
            return
        self.statusBar().showMessage(f"シリアルエラー: {msg}", 5000)
        self._on_disconnected()

    def _on_disconnected(self):
        if not self._connected:
            return
        self._connected = False
        self._conn_btn.setChecked(False)
        self._conn_btn.setText("接続")
        self._worker.disconnect()
        if self._reconnect_port:
            self._status_label.setText(f"切断 — 再接続中... ({self._reconnect_port})")
            self._status_label.setStyleSheet("color: #FFB74D;")
            self._reconnect_timer.start(2000)
        else:
            self._status_label.setText("未接続")
            self._status_label.setStyleSheet("color: gray;")

    def _on_send(self, text: str):
        # text already includes the line ending selected in the console
        if not self._connected:
            self.statusBar().showMessage("未接続のため送信できません", 3000)
            return
        self._worker.send(text.encode("utf-8"))

    # ------------------------------------------------------------------
    def _reset_rx_stats(self):
        self._rx_total = 0
        self._rx_window = 0
        self._rx_window_t = time.monotonic()
        self._update_rx_label()

    def _update_rx_label(self):
        now = time.monotonic()
        dt = now - self._rx_window_t
        rate = self._rx_window / dt if dt > 0 else 0.0
        self._rx_window = 0
        self._rx_window_t = now
        self._rx_label.setText(
            f"受信: {_format_bytes(self._rx_total)}  |  {_format_bytes(rate)}/s"
        )

    # ------------------------------------------------------------------
    # Persist settings between launches
    def _load_settings(self):
        st = self._settings
        baud = st.value("baud", "", type=str)
        if baud in _BAUD_RATES:
            self._baud_combo.setCurrentText(baud)
        self._last_port = st.value("port", "", type=str)
        interval = st.value("interval_ms", 0, type=int)
        if interval:
            self._interval_spin.setValue(interval)
        self._console.set_line_ending_index(st.value("line_ending", 0, type=int))
        geom = st.value("geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        cfg_json = st.value("protocol", "", type=str)
        if cfg_json:
            try:
                self._config = ProtocolConfig.from_dict(json.loads(cfg_json))
                self._parser.set_config(self._config)
                names = self._channel_names_from_config()
                if names:
                    self._graph.set_channels(names)
            except (ValueError, TypeError, AttributeError):
                self._config = ProtocolConfig()

    def _save_settings(self):
        st = self._settings
        st.setValue("baud", self._baud_combo.currentText())
        port = self._reconnect_port or self._port_combo.currentText()
        if port:
            st.setValue("port", port)
        st.setValue("interval_ms", self._interval_spin.value())
        st.setValue("line_ending", self._console.line_ending_index())
        st.setValue("geometry", self.saveGeometry())
        st.setValue("protocol", json.dumps(self._config.to_dict()))

    def _on_tab_changed(self, index: int):
        if self._tabs.widget(index) is self._analysis:
            self._analysis.refresh()

    def closeEvent(self, event):
        self._save_settings()
        self._display_timer.stop()
        self._rx_timer.stop()
        self._reconnect_timer.stop()
        self._worker.disconnect()
        event.accept()
