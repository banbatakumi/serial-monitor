from collections import deque

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QCheckBox, QLineEdit, QLabel, QFileDialog, QComboBox,
)
from PyQt6.QtGui import QTextCursor, QFont
from PyQt6.QtCore import pyqtSignal


_LINE_ENDINGS = [
    ("LF (\\n)",     "\n"),
    ("CRLF (\\r\\n)", "\r\n"),
    ("CR (\\r)",     "\r"),
    ("なし",          ""),
]

# Lines kept in memory for "ログ保存" (older lines are discarded)
_MAX_LOG_LINES = 1_000_000


class ConsoleWidget(QWidget):
    send_requested = pyqtSignal(str)   # text including the selected line ending

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_lines = 5000
        self._log: deque[str] = deque(maxlen=_MAX_LOG_LINES)
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
        self._eol_combo = QComboBox()
        for label, _ in _LINE_ENDINGS:
            self._eol_combo.addItem(label)
        self._eol_combo.setToolTip("送信時に付加する改行コード")
        send_row.addWidget(self._eol_combo)
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
        self.append_lines([line])

    def append_lines(self, lines: list[str]):
        """Append many lines with a single document update (much faster)."""
        if not lines:
            return
        self._log.extend(lines)
        # Only the last _max_lines can remain visible anyway
        self._text.appendPlainText("\n".join(lines[-self._max_lines:]))
        if self._autoscroll.isChecked():
            self._text.moveCursor(QTextCursor.MoveOperation.End)

    def line_ending(self) -> str:
        return _LINE_ENDINGS[self._eol_combo.currentIndex()][1]

    def set_line_ending_index(self, idx: int):
        if 0 <= idx < self._eol_combo.count():
            self._eol_combo.setCurrentIndex(idx)

    def line_ending_index(self) -> int:
        return self._eol_combo.currentIndex()

    def clear(self):
        self._text.clear()
        self._log.clear()

    def _on_send(self):
        text = self._send_edit.text()
        if text:
            self.send_requested.emit(text + self.line_ending())
            self._send_edit.clear()

    def _save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "ログ保存", "", "Text Files (*.txt);;All Files (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self._log))
