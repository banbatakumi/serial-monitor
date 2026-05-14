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
        if not self._channels:
            return
        names = self.channel_names()
        arrays = {n: self._channels[n].to_arrays() for n in names}
        ref_ts = arrays[names[0]][0]

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time_s"] + names)
            for i, t in enumerate(ref_ts):
                row = [f"{t:.6f}"]
                for n in names:
                    ts_arr, val_arr = arrays[n]
                    row.append(f"{val_arr[i]:.6f}" if i < len(val_arr) else "")
                writer.writerow(row)
