from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QCheckBox,
)
from PyQt6.QtCore import Qt

COLORS = [
    "#4FC3F7", "#81C784", "#FFB74D", "#F06292",
    "#CE93D8", "#80DEEA", "#FFCC02", "#FF7043",
]


class RealtimeGraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._window = 200          # samples to show
        self._channels: dict[str, dict] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("表示サンプル数:"))
        self._win_spin = QSpinBox()
        self._win_spin.setRange(10, 10000)
        self._win_spin.setValue(self._window)
        self._win_spin.valueChanged.connect(self._on_window_changed)
        ctrl.addWidget(self._win_spin)

        self._pause_btn = QPushButton("一時停止")
        self._pause_btn.setCheckable(True)
        ctrl.addWidget(self._pause_btn)

        clear_btn = QPushButton("クリア")
        clear_btn.clicked.connect(self.clear)
        ctrl.addWidget(clear_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Plot
        pg.setConfigOption("background", "#1e1e1e")
        pg.setConfigOption("foreground", "#cccccc")
        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.addLegend()
        self._plot.setLabel("bottom", "経過時間 (s)")
        self._plot.setLabel("left", "値")
        layout.addWidget(self._plot)

        # Channel visibility checkboxes row
        self._vis_row = QHBoxLayout()
        self._vis_row.addWidget(QLabel("表示:"))
        self._vis_row.addStretch()
        layout.addLayout(self._vis_row)

    def set_channels(self, names: list[str]):
        # Remove old curves
        for ch in self._channels.values():
            self._plot.removeItem(ch["curve"])
            if ch.get("checkbox"):
                ch["checkbox"].setParent(None)
        self._channels.clear()

        for i, name in enumerate(names):
            color = COLORS[i % len(COLORS)]
            pen = pg.mkPen(color=color, width=2)
            curve = self._plot.plot([], [], name=name, pen=pen)
            buf_ts: deque[float] = deque(maxlen=100_000)
            buf_val: deque[float] = deque(maxlen=100_000)

            cb = QCheckBox(f"■ {name}")
            cb.setChecked(True)
            cb.setStyleSheet(
                f"color: {color}; font-weight: bold;"
                f"QCheckBox::indicator {{ border: 2px solid {color}; }}"
                f"QCheckBox::indicator:checked {{ background-color: {color}; }}"
            )
            cb.stateChanged.connect(lambda state, c=curve: c.setVisible(state == 2))
            self._vis_row.insertWidget(self._vis_row.count() - 1, cb)

            self._channels[name] = {
                "curve": curve,
                "buf_ts": buf_ts,
                "buf_val": buf_val,
                "checkbox": cb,
            }

    def add_sample(self, timestamp: float, values: list[float], channel_names: list[str]):
        if self._pause_btn.isChecked():
            return
        if not self._channels:
            self.set_channels(channel_names)

        for name, val in zip(channel_names, values):
            if name not in self._channels:
                self.set_channels(list(self._channels.keys()) + [name])
            ch = self._channels[name]
            ch["buf_ts"].append(timestamp)
            ch["buf_val"].append(val)

            ts_arr = np.array(ch["buf_ts"])
            val_arr = np.array(ch["buf_val"])
            if len(ts_arr) > self._window:
                ts_arr = ts_arr[-self._window:]
                val_arr = val_arr[-self._window:]
            ch["curve"].setData(ts_arr, val_arr)

    def clear(self):
        for ch in self._channels.values():
            ch["buf_ts"].clear()
            ch["buf_val"].clear()
            ch["curve"].setData([], [])

    def _on_window_changed(self, val: int):
        self._window = val
