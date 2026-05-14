import serial
import serial.tools.list_ports
from PyQt6.QtCore import QThread, pyqtSignal


class SerialWorker(QThread):
    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    disconnected = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._port: serial.Serial | None = None
        self._running = False

    @staticmethod
    def list_ports() -> list[str]:
        ports = serial.tools.list_ports.comports()
        # USB devices (VID is set) come first, then alphabetical
        ports.sort(key=lambda p: (0 if p.vid is not None else 1, p.device))
        return [p.device for p in ports]

    def connect(self, port: str, baud: int, bytesize: int = 8,
                parity: str = 'N', stopbits: float = 1, timeout: float = 0.1) -> bool:
        try:
            self._port = serial.Serial(
                port=port,
                baudrate=baud,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout,
            )
            self._running = True
            self.start()
            return True
        except serial.SerialException as e:
            self.error_occurred.emit(str(e))
            return False

    def disconnect(self):
        self._running = False
        self.wait(2000)
        if self._port and self._port.is_open:
            self._port.close()
        self._port = None

    def send(self, data: bytes):
        if self._port and self._port.is_open:
            try:
                self._port.write(data)
            except serial.SerialException as e:
                self.error_occurred.emit(str(e))

    def run(self):
        while self._running:
            try:
                if self._port and self._port.in_waiting > 0:
                    data = self._port.read(self._port.in_waiting)
                    if data:
                        self.data_received.emit(data)
                else:
                    self.msleep(5)
            except serial.SerialException as e:
                self.error_occurred.emit(str(e))
                break
        self.disconnected.emit()
