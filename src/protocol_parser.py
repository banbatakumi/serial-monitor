import time
from dataclasses import dataclass, field
from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class ProtocolConfig:
    mode: str = "plain"          # "plain" or "structured"
    header: bytes = b""          # b"" means no header (newline-based)
    footer: bytes = b"\n"        # b"\n" means newline-terminated
    separator: str = ","
    channels: list[str] = field(default_factory=list)
    header_is_hex: bool = False  # True: header bytes are raw hex, False: UTF-8 string
    footer_is_hex: bool = False


def _parse_pattern(text: str, is_hex: bool) -> bytes:
    """Convert user-entered pattern string to bytes."""
    text = text.strip()
    if not text:
        return b""
    if is_hex:
        try:
            return bytes(int(b, 16) for b in text.split())
        except ValueError:
            return b""
    return text.encode("utf-8").replace(b"\\n", b"\n").replace(b"\\r", b"\r")


class ProtocolParser(QObject):
    text_line_received = pyqtSignal(str)              # plain text mode
    structured_received = pyqtSignal(float, list)     # (timestamp, [float, ...])

    def __init__(self, config: ProtocolConfig | None = None):
        super().__init__()
        self._config = config or ProtocolConfig()
        self._buf = b""

    def set_config(self, config: ProtocolConfig):
        self._config = config
        self._buf = b""

    def reset(self):
        self._buf = b""

    def feed(self, data: bytes):
        self._buf += data
        cfg = self._config

        if cfg.mode == "plain":
            self._parse_plain()
        else:
            self._parse_structured()

    # ------------------------------------------------------------------
    def _parse_plain(self):
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            text = line.rstrip(b"\r").decode("utf-8", errors="replace")
            if text:
                self.text_line_received.emit(text)

    def _parse_structured(self):
        cfg = self._config
        header = cfg.header
        footer = cfg.footer if cfg.footer else b"\n"

        while True:
            if header:
                idx = self._buf.find(header)
                if idx == -1:
                    # Keep last len(header)-1 bytes in case header spans reads
                    keep = max(0, len(self._buf) - len(header) + 1)
                    self._buf = self._buf[keep:]
                    break
                self._buf = self._buf[idx + len(header):]

            end = self._buf.find(footer)
            if end == -1:
                break

            payload = self._buf[:end]
            self._buf = self._buf[end + len(footer):]

            # Also emit as plain text for the console
            self.text_line_received.emit(payload.decode("utf-8", errors="replace"))

            # Parse numeric values
            values = self._extract_values(payload, cfg)
            if values:
                self.structured_received.emit(time.time(), values)

    def _extract_values(self, payload: bytes, cfg: ProtocolConfig) -> list[float]:
        text = payload.decode("utf-8", errors="replace").strip()
        parts = [p.strip() for p in text.split(cfg.separator)]
        result = []
        for p in parts:
            try:
                result.append(float(p))
            except ValueError:
                pass
        return result
