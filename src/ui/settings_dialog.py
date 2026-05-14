from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QLineEdit, QPushButton, QLabel, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox,
    QRadioButton, QButtonGroup, QDoubleSpinBox, QStackedWidget, QWidget,
)
from PyQt6.QtCore import Qt
from src.protocol_parser import ProtocolConfig, BinaryField, FIELD_TYPES


class SettingsDialog(QDialog):
    def __init__(self, config: ProtocolConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("プロトコル設定")
        self.setMinimumWidth(580)
        self._build_ui(config)

    # ------------------------------------------------------------------
    def _build_ui(self, cfg: ProtocolConfig):
        layout = QVBoxLayout(self)

        # --- Mode selection ---
        mode_group = QGroupBox("受信モード")
        mode_layout = QVBoxLayout(mode_group)

        self._rb_plain  = QRadioButton("テキスト  —  受信行をコンソール表示 / \"Key: value\" 形式は自動でグラフ表示")
        self._rb_csv    = QRadioButton("CSV 数値データ  —  カンマ区切り数値をグラフ表示 (例: 1.57,10.5,0.5)")
        self._rb_binary = QRadioButton("バイナリ  —  ヘッダ・フッタ付きバイナリパケット")

        self._mode_bg = QButtonGroup()
        for rb in (self._rb_plain, self._rb_csv, self._rb_binary):
            self._mode_bg.addButton(rb)
            mode_layout.addWidget(rb)
        layout.addWidget(mode_group)

        # --- Stacked pane (mode-specific settings) ---
        self._stack = QStackedWidget()

        # ── Pane 0: plain (no settings needed) ──
        plain_pane = QWidget()
        plain_layout = QVBoxLayout(plain_pane)
        plain_layout.setContentsMargins(0, 0, 0, 0)
        plain_label = QLabel(
            "設定不要です。\n"
            "受信した文字列をコンソールに表示します。\n"
            "「ラベル: 値」の形式 (例: Theta: 1.23 deg, Speed: 456 rpm) が\n"
            "含まれていれば自動的に検出してリアルタイムグラフにプロットします。"
        )
        plain_label.setStyleSheet("color: gray; padding: 8px;")
        plain_layout.addWidget(plain_label)
        plain_layout.addStretch()
        self._stack.addWidget(plain_pane)

        # ── Pane 1: CSV ──
        csv_pane = QGroupBox("CSV 数値データ 設定")
        csv_form = QFormLayout(csv_pane)

        self._sep_edit = QLineEdit(",")
        self._sep_edit.setMaximumWidth(60)
        csv_form.addRow("区切り文字:", self._sep_edit)

        self._ch_table = QTableWidget(0, 1)
        self._ch_table.setHorizontalHeaderLabels(["チャンネル名 (グラフ用)"])
        self._ch_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._ch_table.setFixedHeight(120)
        csv_form.addRow("チャンネル名:", self._ch_table)

        ch_btn_row = QHBoxLayout()
        add_ch_btn = QPushButton("追加")
        del_ch_btn = QPushButton("削除")
        add_ch_btn.clicked.connect(self._add_channel)
        del_ch_btn.clicked.connect(self._del_channel)
        ch_btn_row.addWidget(add_ch_btn)
        ch_btn_row.addWidget(del_ch_btn)
        ch_btn_row.addStretch()
        csv_form.addRow(ch_btn_row)

        csv_hint = QLabel(
            "【任意】ヘッダ / フッタ\n"
            "データ行をマーカーで囲んでいる場合のみ設定してください。\n"
            "例: ヘッダ「START」フッタ「END」→ START1.57,10.5END"
        )
        csv_hint.setStyleSheet("color: gray; font-size: 11px; padding-top: 6px;")
        csv_form.addRow(csv_hint)

        self._csv_header_edit = QLineEdit()
        self._csv_header_edit.setPlaceholderText("空欄 = なし")
        csv_form.addRow("ヘッダ (任意):", self._csv_header_edit)

        self._csv_footer_edit = QLineEdit()
        self._csv_footer_edit.setPlaceholderText("空欄 = 改行 \\n")
        csv_form.addRow("フッタ (任意):", self._csv_footer_edit)

        self._stack.addWidget(csv_pane)

        # ── Pane 2: binary ──
        bin_pane = QGroupBox("バイナリ設定")
        bin_layout = QVBoxLayout(bin_pane)

        hf_form = QFormLayout()
        self._bin_header_edit = QLineEdit()
        self._bin_header_edit.setPlaceholderText("例: FF")
        hf_form.addRow("ヘッダ (HEX):", self._bin_header_edit)

        self._bin_footer_edit = QLineEdit()
        self._bin_footer_edit.setPlaceholderText("例: AA")
        hf_form.addRow("フッタ (HEX):", self._bin_footer_edit)
        bin_layout.addLayout(hf_form)

        bin_layout.addWidget(QLabel("フィールド定義:"))

        self._bin_table = QTableWidget(0, 5)
        self._bin_table.setHorizontalHeaderLabels(["名前", "型", "スケール(÷)", "エンディアン", "グラフ"])
        hdr = self._bin_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._bin_table.setMinimumHeight(160)
        bin_layout.addWidget(self._bin_table)

        endian_hint = QLabel(
            "エンディアン: 2バイト以上の値のバイト順\n"
            "  Big Endian    — 上位バイトが先  例) 0x1234 → 12 34\n"
            "  Little Endian — 下位バイトが先  例) 0x1234 → 34 12\n"
            "  ※ STM32 は内部的にリトルエンディアン。\n"
            "    手動で >> 8 してバイトを並べている場合はビッグエンディアン。"
        )
        endian_hint.setStyleSheet("color: gray; font-size: 11px;")
        bin_layout.addWidget(endian_hint)

        bin_btn_row = QHBoxLayout()
        add_bin_btn = QPushButton("フィールド追加")
        del_bin_btn = QPushButton("削除")
        add_bin_btn.clicked.connect(lambda: self._add_binary_field())
        del_bin_btn.clicked.connect(self._del_binary_field)
        bin_btn_row.addWidget(add_bin_btn)
        bin_btn_row.addWidget(del_bin_btn)
        bin_btn_row.addStretch()
        bin_layout.addLayout(bin_btn_row)

        self._stack.addWidget(bin_pane)

        layout.addWidget(self._stack)

        # --- OK / Cancel ---
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Populate and wire
        self._load_config(cfg)
        for rb in (self._rb_plain, self._rb_csv, self._rb_binary):
            rb.toggled.connect(self._on_mode_changed)

    # ------------------------------------------------------------------
    def _load_config(self, cfg: ProtocolConfig):
        if cfg.mode == "binary":
            self._rb_binary.setChecked(True)
        elif cfg.mode == "structured":
            self._rb_csv.setChecked(True)
        else:  # "plain" or legacy "labeled"
            self._rb_plain.setChecked(True)

        self._sep_edit.setText(cfg.separator or ",")

        # CSV header/footer
        self._csv_header_edit.setText(self._bytes_to_str(cfg.header, False))
        footer_str = self._bytes_to_str(cfg.footer, False)
        self._csv_footer_edit.setText("" if cfg.footer == b"\n" else footer_str)

        # Binary header/footer
        self._bin_header_edit.setText(" ".join(f"{b:02X}" for b in cfg.header) if cfg.header else "")
        self._bin_footer_edit.setText(" ".join(f"{b:02X}" for b in cfg.footer) if cfg.footer and cfg.footer != b"\n" else "")

        self._ch_table.setRowCount(0)
        for ch in cfg.channels:
            self._add_channel(ch)

        self._bin_table.setRowCount(0)
        for bf in cfg.binary_fields:
            self._add_binary_field(bf)

        self._on_mode_changed()

    @staticmethod
    def _bytes_to_str(b: bytes, is_hex: bool) -> str:
        if not b:
            return ""
        if is_hex:
            return " ".join(f"{x:02X}" for x in b)
        try:
            return b.decode("utf-8").replace("\n", "\\n").replace("\r", "\\r")
        except Exception:
            return ""

    def _on_mode_changed(self):
        if self._rb_plain.isChecked():
            self._stack.setCurrentIndex(0)
        elif self._rb_csv.isChecked():
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(2)

    # --- CSV channels ---
    def _add_channel(self, name: str = ""):
        row = self._ch_table.rowCount()
        self._ch_table.insertRow(row)
        self._ch_table.setItem(row, 0, QTableWidgetItem(name or f"ch{row + 1}"))

    def _del_channel(self):
        for row in sorted({i.row() for i in self._ch_table.selectedIndexes()}, reverse=True):
            self._ch_table.removeRow(row)

    # --- Binary fields ---
    def _add_binary_field(self, bf: BinaryField | None = None):
        row = self._bin_table.rowCount()
        self._bin_table.insertRow(row)

        self._bin_table.setItem(row, 0, QTableWidgetItem(bf.name if bf else f"field{row + 1}"))

        type_cb = QComboBox()
        type_cb.addItems(list(FIELD_TYPES.keys()))
        if bf:
            type_cb.setCurrentText(bf.ftype)
        self._bin_table.setCellWidget(row, 1, type_cb)

        scale_spin = QDoubleSpinBox()
        scale_spin.setRange(0.0001, 1_000_000)
        scale_spin.setDecimals(4)
        scale_spin.setValue(bf.scale if bf else 1.0)
        self._bin_table.setCellWidget(row, 2, scale_spin)

        endian_cb = QComboBox()
        endian_cb.addItems(["big", "little"])
        if bf:
            endian_cb.setCurrentText(bf.endian)
        self._bin_table.setCellWidget(row, 3, endian_cb)

        graph_cb = QCheckBox()
        graph_cb.setChecked(bf.graph if bf else True)
        graph_cb.setStyleSheet("margin-left: 12px;")
        self._bin_table.setCellWidget(row, 4, graph_cb)

    def _del_binary_field(self):
        for row in sorted({i.row() for i in self._bin_table.selectedIndexes()}, reverse=True):
            self._bin_table.removeRow(row)

    # ------------------------------------------------------------------
    def get_config(self) -> ProtocolConfig:
        if self._rb_binary.isChecked():
            mode = "binary"
        elif self._rb_csv.isChecked():
            mode = "structured"
        else:
            mode = "plain"

        if mode == "binary":
            header = self._hex_to_bytes(self._bin_header_edit.text())
            footer_text = self._bin_footer_edit.text().strip()
            footer = self._hex_to_bytes(footer_text) if footer_text else b"\n"
            header_is_hex = True
            footer_is_hex = True
        else:
            header = self._str_to_bytes(self._csv_header_edit.text())
            footer_text = self._csv_footer_edit.text().strip()
            footer = self._str_to_bytes(footer_text) if footer_text else b"\n"
            header_is_hex = False
            footer_is_hex = False

        channels = []
        for row in range(self._ch_table.rowCount()):
            item = self._ch_table.item(row, 0)
            channels.append(item.text().strip() if item else f"ch{row + 1}")

        binary_fields = []
        for row in range(self._bin_table.rowCount()):
            name_item = self._bin_table.item(row, 0)
            name  = name_item.text().strip() if name_item else f"field{row + 1}"
            ftype = self._bin_table.cellWidget(row, 1).currentText()
            scale = self._bin_table.cellWidget(row, 2).value()
            endian = self._bin_table.cellWidget(row, 3).currentText()
            graph = self._bin_table.cellWidget(row, 4).isChecked()
            binary_fields.append(BinaryField(name=name, ftype=ftype, scale=scale, endian=endian, graph=graph))

        return ProtocolConfig(
            mode=mode,
            header=header,
            footer=footer,
            separator=self._sep_edit.text() or ",",
            channels=channels,
            header_is_hex=header_is_hex,
            footer_is_hex=footer_is_hex,
            binary_fields=binary_fields,
        )

    @staticmethod
    def _hex_to_bytes(text: str) -> bytes:
        text = text.strip()
        if not text:
            return b""
        try:
            return bytes(int(b, 16) for b in text.split())
        except ValueError:
            return b""

    @staticmethod
    def _str_to_bytes(text: str) -> bytes:
        text = text.strip()
        if not text:
            return b""
        return text.encode("utf-8").replace(b"\\n", b"\n").replace(b"\\r", b"\r")
