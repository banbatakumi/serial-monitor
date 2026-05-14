from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDoubleSpinBox, QCheckBox,
)
from PyQt6.QtCore import Qt

COLORS = [
    "#4FC3F7", "#81C784", "#FFB74D", "#F06292",
    "#CE93D8", "#80DEEA", "#FFCC02", "#FF7043",
]

_STYLE_FOLLOWING = "QPushButton { background-color: #81C784; color: #1a1a1a; font-weight: bold; }"
_STYLE_DETACHED  = "QPushButton { background-color: #FF7043; color: white;   font-weight: bold; }"


class RealtimeGraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._time_window = 10.0       # seconds to display
        self._channels: dict[str, dict] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controls
        ctrl = QHBoxLayout()

        ctrl.addWidget(QLabel("表示時間:"))
        self._time_spin = QDoubleSpinBox()
        self._time_spin.setRange(0.5, 3600)
        self._time_spin.setValue(self._time_window)
        self._time_spin.setSuffix(" 秒")
        self._time_spin.setDecimals(1)
        self._time_spin.setSingleStep(1.0)
        self._time_spin.setFixedWidth(90)
        self._time_spin.valueChanged.connect(self._on_time_window_changed)
        ctrl.addWidget(self._time_spin)

        self._follow_btn = QPushButton("● 追従中")
        self._follow_btn.setCheckable(True)
        self._follow_btn.setChecked(True)
        self._follow_btn.setFixedWidth(100)
        self._follow_btn.setStyleSheet(_STYLE_FOLLOWING)
        self._follow_btn.clicked.connect(self._on_follow_clicked)
        ctrl.addWidget(self._follow_btn)

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
        self._plot.setLimits(xMin=0)
        self._plot.enableAutoRange(axis='x', enable=False)
        layout.addWidget(self._plot)

        # Detect manual zoom/pan → disable auto-follow
        self._plot.getViewBox().sigRangeChangedManually.connect(self._on_manual_range_change)

        # Channel visibility + scale row
        self._vis_row = QHBoxLayout()
        self._vis_row.addWidget(QLabel("表示:"))
        self._vis_row.addStretch()
        layout.addLayout(self._vis_row)

    # ------------------------------------------------------------------
    def set_channels(self, names: list[str]):
        for ch in self._channels.values():
            self._plot.removeItem(ch["curve"])
            for key in ("checkbox", "scale_label", "scale_spin"):
                w = ch.get(key)
                if w:
                    self._vis_row.removeWidget(w)
                    w.setParent(None)
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

            scale_label = QLabel("×")
            scale_label.setStyleSheet(f"color: {color};")

            scale_spin = QDoubleSpinBox()
            scale_spin.setRange(-1e6, 1e6)
            scale_spin.setValue(1.0)
            scale_spin.setDecimals(3)
            scale_spin.setSingleStep(0.1)
            scale_spin.setFixedWidth(80)
            scale_spin.valueChanged.connect(lambda val, n=name: self._on_scale_changed(n, val))

            pos = self._vis_row.count() - 1
            self._vis_row.insertWidget(pos,     cb)
            self._vis_row.insertWidget(pos + 1, scale_label)
            self._vis_row.insertWidget(pos + 2, scale_spin)

            self._channels[name] = {
                "curve": curve,
                "buf_ts": buf_ts,
                "buf_val": buf_val,
                "checkbox": cb,
                "scale_label": scale_label,
                "scale_spin": scale_spin,
                "scale": 1.0,
            }

    def add_sample(self, timestamp: float, values: list[float], channel_names: list[str]):
        if self._pause_btn.isChecked():
            return
        if not self._channels:
            self.set_channels(channel_names)

        window = self._time_window
        for name, val in zip(channel_names, values):
            if name not in self._channels:
                self.set_channels(list(self._channels.keys()) + [name])
            ch = self._channels[name]
            ch["buf_ts"].append(timestamp)
            ch["buf_val"].append(val)

            ts_arr  = np.array(ch["buf_ts"])
            val_arr = np.array(ch["buf_val"])
            mask = ts_arr >= (timestamp - window)
            ch["curve"].setData(ts_arr[mask], val_arr[mask] * ch["scale"])

        if self._follow_btn.isChecked():
            self._plot.setXRange(max(0.0, timestamp - window), timestamp, padding=0)

    # ------------------------------------------------------------------
    def _on_manual_range_change(self, axes):
        # axes = (x_changed, y_changed); disable follow when X is panned/zoomed
        if axes[0] and self._follow_btn.isChecked():
            self._follow_btn.setChecked(False)
            self._follow_btn.setText("追従オフ — クリックで復帰")
            self._follow_btn.setStyleSheet(_STYLE_DETACHED)
            self._follow_btn.setFixedWidth(180)

    def _on_follow_clicked(self, checked: bool):
        if checked:
            self._follow_btn.setText("● 追従中")
            self._follow_btn.setStyleSheet(_STYLE_FOLLOWING)
            self._follow_btn.setFixedWidth(100)
            self._plot.enableAutoRange(axis='y', enable=True)
            self._scroll_to_latest()

    def _on_time_window_changed(self, val: float):
        self._time_window = val
        if self._follow_btn.isChecked():
            self._scroll_to_latest()

    def _on_scale_changed(self, name: str, val: float):
        ch = self._channels.get(name)
        if not ch:
            return
        ch["scale"] = val
        ts_arr  = np.array(ch["buf_ts"])
        val_arr = np.array(ch["buf_val"])
        if len(ts_arr) == 0:
            return
        mask = ts_arr >= (ts_arr[-1] - self._time_window)
        ch["curve"].setData(ts_arr[mask], val_arr[mask] * val)

    def _scroll_to_latest(self):
        latest = None
        for ch in self._channels.values():
            if ch["buf_ts"]:
                t = ch["buf_ts"][-1]
                if latest is None or t > latest:
                    latest = t
        if latest is not None:
            self._plot.setXRange(max(0.0, latest - self._time_window), latest, padding=0)

    def clear(self):
        for ch in self._channels.values():
            ch["buf_ts"].clear()
            ch["buf_val"].clear()
            ch["curve"].setData([], [])
