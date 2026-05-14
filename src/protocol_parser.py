import re
import struct
import time
from dataclasses import dataclass, field
from PyQt6.QtCore import QObject, pyqtSignal

# Matches patterns like  "Label: value"  "Label: mValue unit"  "Label: -1.23e4"
_LABEL_RE = re.compile(
    r'([A-Za-z_]\w*)'                          # label
    r'\s*:\s*'                                  # colon
    r'[^\d\-+.]*?'                             # optional non-numeric prefix (e.g. "m")
    r'([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)'      # number
)

FIELD_TYPES: dict[str, tuple[str, int]] = {
    "uint8":   ("B", 1),
    "int8":    ("b", 1),
    "uint16":  ("H", 2),
    "int16":   ("h", 2),
    "uint32":  ("I", 4),
    "int32":   ("i", 4),
    "float32": ("f", 4),
}


@dataclass
class BinaryField:
    name: str = ""
    ftype: str = "int16"    # key in FIELD_TYPES
    scale: float = 1.0      # actual_value = raw / scale
    endian: str = "big"     # "big" or "little"
    graph: bool = True


@dataclass
class ProtocolConfig:
    mode: str = "plain"              # "plain" | "labeled" | "structured" | "binary"
    header: bytes = b""
    footer: bytes = b"\n"
    separator: str = ","
    channels: list[str] = field(default_factory=list)
    header_is_hex: bool = False
    footer_is_hex: bool = False
    binary_fields: list[BinaryField] = field(default_factory=list)


class ProtocolParser(QObject):
    text_line_received = pyqtSignal(str)
    structured_received = pyqtSignal(float, list, list)  # (timestamp, values, names)

    def __init__(self, config: ProtocolConfig | None = None):
        super().__init__()
        self._config = config or ProtocolConfig()
        self._buf = b""
        self._t0: float | None = None

    def set_config(self, config: ProtocolConfig):
        self._config = config
        self._buf = b""

    def reset(self):
        self._buf = b""
        self._t0 = None

    def _now(self) -> float:
        t = time.time()
        if self._t0 is None:
            self._t0 = t
        return t - self._t0

    def feed(self, data: bytes):
        self._buf += data
        if self._config.mode in ("plain", "labeled"):
            self._parse_plain()
        elif self._config.mode == "binary":
            self._parse_binary()
        else:
            self._parse_text_structured()

    # ------------------------------------------------------------------
    def _parse_plain(self):
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            text = line.rstrip(b"\r").decode("utf-8", errors="replace")
            if not text:
                continue
            self.text_line_received.emit(text)
            matches = _LABEL_RE.findall(text)
            if matches:
                names  = [m[0] for m in matches]
                values = [float(m[1]) for m in matches]
                self.structured_received.emit(self._now(), values, names)

    def _parse_text_structured(self):
        cfg = self._config
        header = cfg.header
        footer = cfg.footer if cfg.footer else b"\n"

        while True:
            if header:
                idx = self._buf.find(header)
                if idx == -1:
                    keep = max(0, len(self._buf) - len(header) + 1)
                    self._buf = self._buf[keep:]
                    break
                self._buf = self._buf[idx + len(header):]

            end = self._buf.find(footer)
            if end == -1:
                break

            payload = self._buf[:end]
            self._buf = self._buf[end + len(footer):]

            text = payload.decode("utf-8", errors="replace")
            self.text_line_received.emit(text)

            values = self._extract_csv_values(text, cfg.separator)
            if values:
                self.structured_received.emit(self._now(), values, [])

    def _parse_binary(self):
        cfg = self._config
        header = cfg.header
        footer = cfg.footer

        payload_size = sum(
            FIELD_TYPES[f.ftype][1]
            for f in cfg.binary_fields
            if f.ftype in FIELD_TYPES
        )

        while True:
            # Search for header
            if header:
                idx = self._buf.find(header)
                if idx == -1:
                    keep = max(0, len(self._buf) - len(header) + 1)
                    self._buf = self._buf[keep:]
                    break
                if idx > 0:
                    self._buf = self._buf[idx:]
                self._buf = self._buf[len(header):]

            # Need: payload_size + footer bytes
            needed = payload_size + (len(footer) if footer else 0)
            if len(self._buf) < needed:
                break

            payload = self._buf[:payload_size]

            # Validate footer
            if footer:
                actual_footer = self._buf[payload_size: payload_size + len(footer)]
                if actual_footer != footer:
                    # Mismatch: discard one byte and retry
                    self._buf = self._buf[1:]
                    continue
                self._buf = self._buf[payload_size + len(footer):]
            else:
                self._buf = self._buf[payload_size:]

            values, names, console_parts = self._decode_binary_payload(payload, cfg.binary_fields)
            self.text_line_received.emit("  ".join(console_parts))
            if values:
                self.structured_received.emit(self._now(), values, [])

    # ------------------------------------------------------------------
    @staticmethod
    def _decode_binary_payload(
        payload: bytes, fields: list[BinaryField]
    ) -> tuple[list[float], list[str], list[str]]:
        values: list[float] = []
        names: list[str] = []
        console_parts: list[str] = []
        offset = 0

        for f in fields:
            if f.ftype not in FIELD_TYPES:
                continue
            fmt, size = FIELD_TYPES[f.ftype]
            if offset + size > len(payload):
                break
            endian_char = ">" if f.endian == "big" else "<"
            (raw,) = struct.unpack_from(endian_char + fmt, payload, offset)
            val = raw / f.scale if f.scale != 0 else float(raw)
            offset += size

            label = f.name or f"field{offset}"
            console_parts.append(f"{label}={val:.4f}")

            if f.graph:
                values.append(val)
                names.append(label)

        return values, names, console_parts

    @staticmethod
    def _extract_csv_values(text: str, sep: str) -> list[float]:
        result = []
        for part in text.split(sep):
            try:
                result.append(float(part.strip()))
            except ValueError:
                pass
        return result
