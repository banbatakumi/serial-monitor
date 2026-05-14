import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QComboBox, QFileDialog, QCheckBox,
)
from PyQt6.QtCore import Qt
from src.data_store import DataStore
from src.ui.graph_widget import COLORS


class AnalysisWidget(QWidget):
    def __init__(self, store: DataStore, parent=None):
        super().__init__(parent)
        self._store = store
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Top controls
        ctrl = QHBoxLayout()
        refresh_btn = QPushButton("更新")
        refresh_btn.clicked.connect(self.refresh)
        ctrl.addWidget(refresh_btn)

        export_btn = QPushButton("CSV エクスポート")
        export_btn.clicked.connect(self._export_csv)
        ctrl.addWidget(export_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Graph
        pg.setConfigOption("background", "#1e1e1e")
        pg.setConfigOption("foreground", "#cccccc")
        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.addLegend()
        self._plot.setLabel("bottom", "経過時間 (s)")
        self._plot.setLabel("left", "値")
        splitter.addWidget(self._plot)

        # Statistics table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["チャンネル", "件数", "平均", "標準偏差", "最小値", "最大値"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self._table)

        splitter.setSizes([400, 200])
        layout.addWidget(splitter)

    def refresh(self):
        self._plot.clear()
        legend = self._plot.addLegend()

        names = self._store.channel_names()
        stats = self._store.all_stats()

        self._table.setRowCount(len(names))
        for row, name in enumerate(names):
            ch = self._store.get_channel(name)
            if ch is None:
                continue
            ts_arr, val_arr = ch.to_arrays()
            color = COLORS[row % len(COLORS)]
            pen = pg.mkPen(color=color, width=2)
            self._plot.plot(ts_arr, val_arr, name=name, pen=pen)

            s = stats.get(name, {})
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(str(s.get("count", ""))))
            self._table.setItem(row, 2, QTableWidgetItem(f'{s.get("mean", ""):.4f}' if s else ""))
            self._table.setItem(row, 3, QTableWidgetItem(f'{s.get("std", ""):.4f}' if s else ""))
            self._table.setItem(row, 4, QTableWidgetItem(f'{s.get("min", ""):.4f}' if s else ""))
            self._table.setItem(row, 5, QTableWidgetItem(f'{s.get("max", ""):.4f}' if s else ""))

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV エクスポート", "", "CSV Files (*.csv)")
        if path:
            self._store.export_csv(path)
