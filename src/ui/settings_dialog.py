from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QLineEdit, QPushButton, QLabel, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox,
    QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt
from src.protocol_parser import ProtocolConfig


class SettingsDialog(QDialog):
    def __init__(self, config: ProtocolConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("プロトコル設定")
        self.setMinimumWidth(500)
        self._build_ui(config)

    def _build_ui(self, cfg: ProtocolConfig):
        layout = QVBoxLayout(self)

        # --- Mode ---
        mode_group = QGroupBox("受信モード")
        mode_layout = QHBoxLayout(mode_group)
        self._rb_plain = QRadioButton("プレーンテキスト (printf)")
        self._rb_struct = QRadioButton("構造化データ (ヘッダ/フッタ)")
        self._mode_bg = QButtonGroup()
        self._mode_bg.addButton(self._rb_plain)
        self._mode_bg.addButton(self._rb_struct)
        mode_layout.addWidget(self._rb_plain)
        mode_layout.addWidget(self._rb_struct)
        layout.addWidget(mode_group)

        # --- Structured settings ---
        self._struct_group = QGroupBox("構造化設定")
        form = QFormLayout(self._struct_group)

        self._header_edit = QLineEdit()
        self._header_hex = QCheckBox("HEX")
        header_row = QHBoxLayout()
        header_row.addWidget(self._header_edit)
        header_row.addWidget(self._header_hex)
        form.addRow("ヘッダ:", header_row)

        self._footer_edit = QLineEdit()
        self._footer_hex = QCheckBox("HEX")
        footer_row = QHBoxLayout()
        footer_row.addWidget(self._footer_edit)
        footer_row.addWidget(self._footer_hex)
        form.addRow("フッタ:", footer_row)

        self._sep_edit = QLineEdit()
        form.addRow("区切り文字:", self._sep_edit)

        layout.addWidget(self._struct_group)

        hint = QLabel(
            "ヘッダ/フッタは文字列または HEX バイト列（例: AA BB CC）で指定\n"
            "空欄の場合: ヘッダなし, フッタ=改行"
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        # --- Channels ---
        ch_group = QGroupBox("チャンネル名 (グラフ用)")
        ch_layout = QVBoxLayout(ch_group)
        self._ch_table = QTableWidget(0, 1)
        self._ch_table.setHorizontalHeaderLabels(["チャンネル名"])
        self._ch_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._ch_table.setFixedHeight(150)
        ch_layout.addWidget(self._ch_table)

        ch_btn_row = QHBoxLayout()
        add_btn = QPushButton("追加")
        del_btn = QPushButton("削除")
        add_btn.clicked.connect(self._add_channel)
        del_btn.clicked.connect(self._del_channel)
        ch_btn_row.addWidget(add_btn)
        ch_btn_row.addWidget(del_btn)
        ch_layout.addLayout(ch_btn_row)
        layout.addWidget(ch_group)

        # --- OK / Cancel ---
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Populate from config
        self._load_config(cfg)

        # Connect mode toggle
        self._rb_plain.toggled.connect(self._on_mode_changed)
        self._rb_struct.toggled.connect(self._on_mode_changed)

    def _load_config(self, cfg: ProtocolConfig):
        if cfg.mode == "plain":
            self._rb_plain.setChecked(True)
        else:
            self._rb_struct.setChecked(True)

        try:
            header_str = cfg.header.decode("utf-8") if cfg.header and not cfg.header_is_hex else \
                         " ".join(f"{b:02X}" for b in cfg.header)
        except Exception:
            header_str = ""
        self._header_edit.setText(header_str)
        self._header_hex.setChecked(cfg.header_is_hex)

        try:
            footer_str = cfg.footer.decode("utf-8") if cfg.footer and not cfg.footer_is_hex else \
                         " ".join(f"{b:02X}" for b in cfg.footer)
        except Exception:
            footer_str = "\\n"
        self._footer_edit.setText(footer_str)
        self._footer_hex.setChecked(cfg.footer_is_hex)

        self._sep_edit.setText(cfg.separator)

        self._ch_table.setRowCount(0)
        for ch in cfg.channels:
            self._add_channel(ch)

        self._on_mode_changed()

    def _on_mode_changed(self):
        self._struct_group.setEnabled(self._rb_struct.isChecked())

    def _add_channel(self, name: str = ""):
        row = self._ch_table.rowCount()
        self._ch_table.insertRow(row)
        item = QTableWidgetItem(name if name else f"ch{row + 1}")
        self._ch_table.setItem(row, 0, item)

    def _del_channel(self):
        rows = {idx.row() for idx in self._ch_table.selectedIndexes()}
        for row in sorted(rows, reverse=True):
            self._ch_table.removeRow(row)

    def get_config(self) -> ProtocolConfig:
        mode = "plain" if self._rb_plain.isChecked() else "structured"
        header_is_hex = self._header_hex.isChecked()
        footer_is_hex = self._footer_hex.isChecked()

        def to_bytes(text: str, is_hex: bool) -> bytes:
            text = text.strip()
            if not text:
                return b""
            if is_hex:
                try:
                    return bytes(int(b, 16) for b in text.split())
                except ValueError:
                    return b""
            return text.encode("utf-8").replace(b"\\n", b"\n").replace(b"\\r", b"\r")

        header = to_bytes(self._header_edit.text(), header_is_hex)
        footer_text = self._footer_edit.text()
        footer = to_bytes(footer_text, footer_is_hex) if footer_text.strip() else b"\n"

        channels = []
        for row in range(self._ch_table.rowCount()):
            item = self._ch_table.item(row, 0)
            if item:
                channels.append(item.text().strip() or f"ch{row + 1}")

        return ProtocolConfig(
            mode=mode,
            header=header,
            footer=footer,
            separator=self._sep_edit.text() or ",",
            channels=channels,
            header_is_hex=header_is_hex,
            footer_is_hex=footer_is_hex,
        )
