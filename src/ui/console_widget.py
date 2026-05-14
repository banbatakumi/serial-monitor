from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QCheckBox, QLineEdit, QLabel, QFileDialog,
)
from PyQt6.QtGui import QTextCursor, QFont
from PyQt6.QtCore import pyqtSignal


class ConsoleWidget(QWidget):
    send_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_lines = 5000
        self._log: list[str] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        font = QFont("Menlo", 11)
        self._text.setFont(font)
        self._text.setMaximumBlockCount(self._max_lines)
        layout.addWidget(self._text)

        # Send row
        send_row = QHBoxLayout()
        send_row.addWidget(QLabel("送信:"))
        self._send_edit = QLineEdit()
        self._send_edit.setPlaceholderText("テキストを入力して Enter")
        self._send_edit.returnPressed.connect(self._on_send)
        send_row.addWidget(self._send_edit)
        send_btn = QPushButton("送信")
        send_btn.clicked.connect(self._on_send)
        send_row.addWidget(send_btn)
        layout.addLayout(send_row)

        # Control row
        ctrl_row = QHBoxLayout()
        clear_btn = QPushButton("クリア")
        clear_btn.clicked.connect(self.clear)
        ctrl_row.addWidget(clear_btn)

        self._autoscroll = QCheckBox("自動スクロール")
        self._autoscroll.setChecked(True)
        ctrl_row.addWidget(self._autoscroll)

        save_btn = QPushButton("ログ保存")
        save_btn.clicked.connect(self._save_log)
        ctrl_row.addWidget(save_btn)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

    def append_line(self, line: str):
        self._log.append(line)
        self._text.appendPlainText(line)
        if self._autoscroll.isChecked():
            self._text.moveCursor(QTextCursor.MoveOperation.End)

    def clear(self):
        self._text.clear()
        self._log.clear()

    def _on_send(self):
        text = self._send_edit.text()
        if text:
            self.send_requested.emit(text)
            self._send_edit.clear()

    def _save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "ログ保存", "", "Text Files (*.txt);;All Files (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self._log))
