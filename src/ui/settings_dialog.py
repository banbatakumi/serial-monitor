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
        self.setMinimumWidth(560)
        self._build_ui(config)

    # ------------------------------------------------------------------
    def _build_ui(self, cfg: ProtocolConfig):
        layout = QVBoxLayout(self)

        # --- Mode ---
        mode_group = QGroupBox("受信モード")
        mode_layout = QHBoxLayout(mode_group)
        self._rb_plain  = QRadioButton("プレーンテキスト")
        self._rb_text   = QRadioButton("テキスト構造化 (CSV)")
        self._rb_binary = QRadioButton("バイナリ")
        self._mode_bg   = QButtonGroup()
        for rb in (self._rb_plain, self._rb_text, self._rb_binary):
            self._mode_bg.addButton(rb)
            mode_layout.addWidget(rb)
        layout.addWidget(mode_group)

        # --- Header / Footer (shared) ---
        hf_group = QGroupBox("ヘッダ / フッタ")
        hf_form  = QFormLayout(hf_group)

        self._header_edit = QLineEdit()
        self._header_hex  = QCheckBox("HEX")
        hrow = QHBoxLayout()
        hrow.addWidget(self._header_edit)
        hrow.addWidget(self._header_hex)
        hf_form.addRow("ヘッダ:", hrow)

        self._footer_edit = QLineEdit()
        self._footer_hex  = QCheckBox("HEX")
        frow = QHBoxLayout()
        frow.addWidget(self._footer_edit)
        frow.addWidget(self._footer_hex)
        hf_form.addRow("フッタ:", frow)

        hint = QLabel("文字列 or HEX バイト列（例: FF AA）　空欄=なし / フッタ空欄=改行")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        hf_form.addRow(hint)
        layout.addWidget(hf_group)

        # --- Stacked mode-specific pane ---
        self._stack = QStackedWidget()

        # Pane 0: plain (empty)
        self._stack.addWidget(QWidget())

        # Pane 1: text structured
        text_pane = QGroupBox("テキスト構造化設定")
        text_form = QFormLayout(text_pane)
        self._sep_edit = QLineEdit(",")
        text_form.addRow("区切り文字:", self._sep_edit)

        self._ch_table = QTableWidget(0, 1)
        self._ch_table.setHorizontalHeaderLabels(["チャンネル名"])
        self._ch_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._ch_table.setFixedHeight(130)
        text_form.addRow("チャンネル名:", self._ch_table)

        ch_btn_row = QHBoxLayout()
        add_ch_btn = QPushButton("追加")
        del_ch_btn = QPushButton("削除")
        add_ch_btn.clicked.connect(self._add_channel)
        del_ch_btn.clicked.connect(self._del_channel)
        ch_btn_row.addWidget(add_ch_btn)
        ch_btn_row.addWidget(del_ch_btn)
        text_form.addRow(ch_btn_row)
        self._stack.addWidget(text_pane)

        # Pane 2: binary
        bin_pane = QGroupBox("バイナリフィールド定義")
        bin_layout = QVBoxLayout(bin_pane)

        self._bin_table = QTableWidget(0, 5)
        self._bin_table.setHorizontalHeaderLabels(["名前", "型", "スケール(÷)", "エンディアン", "グラフ"])
        self._bin_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._bin_table.setMinimumHeight(160)
        bin_layout.addWidget(self._bin_table)

        bin_btn_row = QHBoxLayout()
        add_bin_btn = QPushButton("追加")
        del_bin_btn = QPushButton("削除")
        add_bin_btn.clicked.connect(lambda: self._add_binary_field())
        del_bin_btn.clicked.connect(self._del_binary_field)
        bin_btn_row.addWidget(add_bin_btn)
        bin_btn_row.addWidget(del_bin_btn)
        bin_layout.addLayout(bin_btn_row)
        self._stack.addWidget(bin_pane)

        layout.addWidget(self._stack)

        # --- Buttons ---
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Populate & wire
        self._load_config(cfg)
        self._rb_plain.toggled.connect(self._on_mode_changed)
        self._rb_text.toggled.connect(self._on_mode_changed)
        self._rb_binary.toggled.connect(self._on_mode_changed)

    # ------------------------------------------------------------------
    def _load_config(self, cfg: ProtocolConfig):
        if cfg.mode == "binary":
            self._rb_binary.setChecked(True)
        elif cfg.mode == "structured":
            self._rb_text.setChecked(True)
        else:
            self._rb_plain.setChecked(True)

        self._header_edit.setText(self._bytes_to_str(cfg.header, cfg.header_is_hex))
        self._header_hex.setChecked(cfg.header_is_hex)
        self._footer_edit.setText(self._bytes_to_str(cfg.footer, cfg.footer_is_hex))
        self._footer_hex.setChecked(cfg.footer_is_hex)

        self._sep_edit.setText(cfg.separator)

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
            s = b.decode("utf-8")
            return s.replace("\n", "\\n").replace("\r", "\\r")
        except Exception:
            return " ".join(f"{x:02X}" for x in b)

    def _on_mode_changed(self):
        if self._rb_plain.isChecked():
            self._stack.setCurrentIndex(0)
        elif self._rb_text.isChecked():
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(2)

    # --- Text channels ---
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

        name_item = QTableWidgetItem(bf.name if bf else f"field{row + 1}")
        self._bin_table.setItem(row, 0, name_item)

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
        elif self._rb_text.isChecked():
            mode = "structured"
        else:
            mode = "plain"

        header_is_hex = self._header_hex.isChecked()
        footer_is_hex = self._footer_hex.isChecked()
        header = self._str_to_bytes(self._header_edit.text(), header_is_hex)
        footer_text = self._footer_edit.text()
        footer = self._str_to_bytes(footer_text, footer_is_hex) if footer_text.strip() else b"\n"

        channels = []
        for row in range(self._ch_table.rowCount()):
            item = self._ch_table.item(row, 0)
            channels.append(item.text().strip() if item else f"ch{row + 1}")

        binary_fields = []
        for row in range(self._bin_table.rowCount()):
            name_item = self._bin_table.item(row, 0)
            name = name_item.text().strip() if name_item else f"field{row + 1}"
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
    def _str_to_bytes(text: str, is_hex: bool) -> bytes:
        text = text.strip()
        if not text:
            return b""
        if is_hex:
            try:
                return bytes(int(b, 16) for b in text.split())
            except ValueError:
                return b""
        return text.encode("utf-8").replace(b"\\n", b"\n").replace(b"\\r", b"\r")
