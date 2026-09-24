import re
import struct
import time
from dataclasses import asdict, dataclass, field
from PyQt6.QtCore import QObject, pyqtSignal

# Matches patterns like  "Label: value"  "Label: mValue unit"  "Label: -1.23e4"
#                    and "key=value"  "speed=3.14 m/s"  "is_slipping=0"
_LABEL_RE = re.compile(
    r'([A-Za-z_]\w*)'                          # label
    r'\s*[=:]\s*'                              # colon or equals
    r'[^\d\-+.]*?'                             # optional non-numeric prefix (e.g. "m")
    r'([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)'      # number
)

# Max bytes kept while waiting for a line terminator / packet boundary.
# Protects against unbounded growth when the device never sends "\n".
_MAX_BUF = 64 * 1024

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

    def to_dict(self) -> dict:
        """JSON-serializable form (bytes → hex string) for saving settings."""
        return {
            "mode": self.mode,
            "header": self.header.hex(),
            "footer": self.footer.hex(),
            "separator": self.separator,
            "channels": list(self.channels),
            "header_is_hex": self.header_is_hex,
            "footer_is_hex": self.footer_is_hex,
            "binary_fields": [asdict(f) for f in self.binary_fields],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProtocolConfig":
        fields = []
        for fd in d.get("binary_fields", []):
            bf = BinaryField(
                name=str(fd.get("name", "")),
                ftype=str(fd.get("ftype", "int16")),
                scale=float(fd.get("scale", 1.0)),
                endian=str(fd.get("endian", "big")),
                graph=bool(fd.get("graph", True)),
            )
            if bf.ftype in FIELD_TYPES:
                fields.append(bf)
        mode = d.get("mode", "plain")
        if mode not in ("plain", "labeled", "structured", "binary"):
            mode = "plain"
        return cls(
            mode=mode,
            header=bytes.fromhex(d.get("header", "")),
            footer=bytes.fromhex(d.get("footer", "0a")),
            separator=d.get("separator", ",") or ",",
            channels=[str(c) for c in d.get("channels", [])],
            header_is_hex=bool(d.get("header_is_hex", False)),
            footer_is_hex=bool(d.get("footer_is_hex", False)),
            binary_fields=fields,
        )


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

    def reset_buffer(self):
        """Reset receive buffer only; preserves timestamp origin for seamless reconnect."""
        self._buf = b""

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
            self._handle_plain_line(line)
        if len(self._buf) > _MAX_BUF:
            # No newline for a long time: flush what we have as one line
            line, self._buf = self._buf, b""
            self._handle_plain_line(line)

    def _handle_plain_line(self, line: bytes):
        text = line.rstrip(b"\r").decode("utf-8", errors="replace")
        if not text:
            return
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
            start = 0
            if header:
                idx = self._buf.find(header)
                if idx == -1:
                    keep = max(0, len(self._buf) - len(header) + 1)
                    self._buf = self._buf[keep:]
                    break
                # Drop garbage before the header, but keep the header itself
                # until the whole packet has arrived (packets may be split
                # across several reads).
                self._buf = self._buf[idx:]
                start = len(header)

            end = self._buf.find(footer, start)
            if end == -1:
                if len(self._buf) > _MAX_BUF:
                    self._buf = self._buf[start:] if header else b""
                break

            payload = self._buf[start:end]
            self._buf = self._buf[end + len(footer):]

            text = payload.decode("utf-8", errors="replace").rstrip("\r")
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

        if payload_size == 0 and not header and not footer:
            # Nothing defined — cannot delimit packets
            self._buf = b""
            return

        hlen = len(header)
        flen = len(footer) if footer else 0

        while True:
            # Search for header (keep it in the buffer until the whole
            # packet is available — packets may be split across reads)
            if header:
                idx = self._buf.find(header)
                if idx == -1:
                    keep = max(0, len(self._buf) - hlen + 1)
                    self._buf = self._buf[keep:]
                    break
                if idx > 0:
                    self._buf = self._buf[idx:]

            needed = hlen + payload_size + flen
            if len(self._buf) < needed:
                break

            payload = self._buf[hlen: hlen + payload_size]

            # Validate footer
            if footer:
                actual_footer = self._buf[hlen + payload_size: needed]
                if actual_footer != footer:
                    # Mismatch: discard one byte and resync
                    self._buf = self._buf[1:]
                    continue
            self._buf = self._buf[needed:]

            values, names, console_parts = self._decode_binary_payload(payload, cfg.binary_fields)
            self.text_line_received.emit("  ".join(console_parts))
            if values:
                self.structured_received.emit(self._now(), values, names)

    # ------------------------------------------------------------------
    @staticmethod
    def _decode_binary_payload(
        payload: bytes, fields: list[BinaryField]
    ) -> tuple[list[float], list[str], list[str]]:
        values: list[float] = []
        names: list[str] = []
        console_parts: list[str] = []
        offset = 0

        for i, f in enumerate(fields):
            if f.ftype not in FIELD_TYPES:
                continue
            fmt, size = FIELD_TYPES[f.ftype]
            if offset + size > len(payload):
                break
            endian_char = ">" if f.endian == "big" else "<"
            (raw,) = struct.unpack_from(endian_char + fmt, payload, offset)
            val = raw / f.scale if f.scale != 0 else float(raw)
            offset += size

            label = f.name or f"field{i + 1}"
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
