import time

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QLabel, QTabWidget,
    QStatusBar, QMessageBox,
)
from PyQt6.QtCore import QTimer

from src.serial_worker import SerialWorker
from src.protocol_parser import ProtocolParser, ProtocolConfig
from src.data_store import DataStore
from src.ui.console_widget import ConsoleWidget
from src.ui.graph_widget import RealtimeGraphWidget
from src.ui.analysis_widget import AnalysisWidget
from src.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Serial Monitor")
        self.resize(1100, 700)

        self._worker = SerialWorker()
        self._parser = ProtocolParser()
        self._store  = DataStore()
        self._config = ProtocolConfig()
        self._connected = False

        self._build_ui()
        self._connect_signals()

        self._port_timer = QTimer()
        self._port_timer.timeout.connect(self._refresh_ports)
        self._port_timer.start(2000)
        self._refresh_ports()

    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("ポート:"))
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(140)
        toolbar.addWidget(self._port_combo)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(30)
        refresh_btn.clicked.connect(self._refresh_ports)
        toolbar.addWidget(refresh_btn)

        toolbar.addWidget(QLabel("ボーレート:"))
        self._baud_combo = QComboBox()
        for br in ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]:
            self._baud_combo.addItem(br)
        self._baud_combo.setCurrentText("115200")
        toolbar.addWidget(self._baud_combo)

        self._conn_btn = QPushButton("接続")
        self._conn_btn.setCheckable(True)
        self._conn_btn.setMinimumWidth(80)
        self._conn_btn.clicked.connect(self._toggle_connection)
        toolbar.addWidget(self._conn_btn)

        toolbar.addSpacing(20)

        proto_btn = QPushButton("プロトコル設定")
        proto_btn.clicked.connect(self._open_settings)
        toolbar.addWidget(proto_btn)

        toolbar.addStretch()

        self._status_label = QLabel("未接続")
        self._status_label.setStyleSheet("color: gray;")
        toolbar.addWidget(self._status_label)

        root.addLayout(toolbar)

        # Tabs
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

    def _connect_signals(self):
        self._worker.data_received.connect(self._on_raw_data)
        self._worker.error_occurred.connect(self._on_serial_error)
        self._worker.disconnected.connect(self._on_disconnected)

        self._parser.text_line_received.connect(self._on_text_line)
        self._parser.structured_received.connect(self._on_structured)

        self._console.send_requested.connect(self._on_send)

    # ------------------------------------------------------------------
    def _refresh_ports(self):
        current = self._port_combo.currentText()
        ports = SerialWorker.list_ports()
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        self._port_combo.addItems(ports)
        if current in ports:
            self._port_combo.setCurrentText(current)
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
                self._connected = True
                self._conn_btn.setText("切断")
                self._status_label.setText(f"接続中: {port} @ {baud}")
                self._status_label.setStyleSheet("color: #81C784;")
                self._parser.reset()
            else:
                self._conn_btn.setChecked(False)
        else:
            self._disconnect()

    def _disconnect(self):
        self._worker.disconnect()
        self._connected = False
        self._conn_btn.setChecked(False)
        self._conn_btn.setText("接続")
        self._status_label.setText("未接続")
        self._status_label.setStyleSheet("color: gray;")

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

    def _channel_names_from_config(self) -> list[str]:
        if self._config.mode == "binary":
            return [f.name for f in self._config.binary_fields if f.graph and f.name]
        return self._config.channels

    # ------------------------------------------------------------------
    def _on_raw_data(self, data: bytes):
        self._parser.feed(data)

    def _on_text_line(self, line: str):
        self._console.append_line(line)

    def _on_structured(self, timestamp: float, values: list):
        names = self._channel_names_from_config()
        if not names:
            names = [f"ch{i + 1}" for i in range(len(values))]
        names = (names + [f"ch{i + 1}" for i in range(len(names), len(values))])[:len(values)]

        self._store.add_sample(timestamp, values, names)
        self._graph.add_sample(timestamp, values, names)

    def _on_serial_error(self, msg: str):
        self.statusBar().showMessage(f"シリアルエラー: {msg}", 5000)
        self._disconnect()

    def _on_disconnected(self):
        if self._connected:
            self._disconnect()

    def _on_send(self, text: str):
        self._worker.send((text + "\n").encode("utf-8"))

    def _on_tab_changed(self, index: int):
        if self._tabs.widget(index) is self._analysis:
            self._analysis.refresh()

    def closeEvent(self, event):
        self._worker.disconnect()
        event.accept()
