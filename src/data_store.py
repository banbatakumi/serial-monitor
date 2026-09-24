import csv
from collections import deque

import numpy as np


class ChannelBuffer:
    def __init__(self, name: str, maxlen: int = 100_000):
        self.name = name
        self.timestamps: deque[float] = deque(maxlen=maxlen)
        self.values: deque[float] = deque(maxlen=maxlen)

    def append(self, ts: float, val: float):
        self.timestamps.append(ts)
        self.values.append(val)

    def to_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        return np.array(self.timestamps), np.array(self.values)

    def stats(self) -> dict:
        if not self.values:
            return {}
        arr = np.array(self.values)
        return {
            "count": len(arr),
            "mean":  float(np.mean(arr)),
            "std":   float(np.std(arr)),
            "min":   float(np.min(arr)),
            "max":   float(np.max(arr)),
        }


class DataStore:
    def __init__(self, maxlen: int = 100_000):
        self._maxlen = maxlen
        self._channels: dict[str, ChannelBuffer] = {}

    def reset(self):
        self._channels.clear()

    def add_sample(self, timestamp: float, values: list[float], channel_names: list[str]):
        for name, val in zip(channel_names, values):
            if name not in self._channels:
                self._channels[name] = ChannelBuffer(name, self._maxlen)
            self._channels[name].append(timestamp, val)

    def channel_names(self) -> list[str]:
        return list(self._channels.keys())

    def get_channel(self, name: str) -> ChannelBuffer | None:
        return self._channels.get(name)

    def all_stats(self) -> dict[str, dict]:
        return {name: ch.stats() for name, ch in self._channels.items()}

    def export_csv(self, path: str):
        """Write all channels to CSV, one row per timestamp.

        Channels may be sampled at different times (e.g. labeled mode where
        a key appears only on some lines), so rows are merged by timestamp
        instead of by index. Missing values are left empty.
        """
        if not self._channels:
            return
        names = self.channel_names()
        rows: dict[float, dict[str, float]] = {}
        for n in names:
            ch = self._channels[n]
            for t, v in zip(ch.timestamps, ch.values):
                rows.setdefault(t, {})[n] = v

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time_s"] + names)
            for t in sorted(rows):
                vals = rows[t]
                writer.writerow(
                    [f"{t:.6f}"] + [f"{vals[n]:.6f}" if n in vals else "" for n in names]
                )
