import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple


COM_ROOT = r"C:\COM"
NEWBMLOG_DIR = os.path.join(COM_ROOT, "NEWBMLOG")
NEWLOG_DIR = os.path.join(COM_ROOT, "NEWLOG")
CONFIG_PATH = os.path.join(COM_ROOT, "moa_linkageSM_config.json")

DEFAULT_CUT_PATTERNS = [
    bytes.fromhex("1D 56 00"),
    bytes.fromhex("1D 56 01"),
    bytes.fromhex("1D 56 41"),
    bytes.fromhex("1D 56 42"),
    bytes.fromhex("1B 69"),
    bytes.fromhex("1B 6D"),
]


@dataclass
class PortSettings:
    baudrate: int = 9600
    parity: str = "N"
    stopbits: float = 1
    bytesize: int = 8
    flow_control: str = "none"
    encoding: str = "cp949"
    cut_patterns_hex: str = "1D 56 00, 1D 56 01, 1D 56 41, 1D 56 42, 1B 69, 1B 6D"
    idle_timeout_ms: int = 1500
    min_bytes: int = 8


@dataclass
class MonitorConfig:
    selected_ports: List[str]
    port_settings: Dict[str, PortSettings]
    driver_backend_enabled: bool = False
    direct_monitor_enabled: bool = False


def ensure_com_dirs() -> None:
    for path in (COM_ROOT, NEWBMLOG_DIR, NEWLOG_DIR):
        os.makedirs(path, exist_ok=True)


def default_config(ports: Optional[List[str]] = None) -> MonitorConfig:
    selected = []
    settings_ports = [p.upper() for p in ports] if ports else []
    return MonitorConfig(
        selected_ports=selected,
        port_settings={p: PortSettings() for p in settings_ports},
    )


def _settings_from_dict(data: dict) -> PortSettings:
    defaults = asdict(PortSettings())
    defaults.update({k: v for k, v in data.items() if k in defaults})
    return PortSettings(**defaults)


def load_config(available_ports: Optional[List[str]] = None) -> MonitorConfig:
    ensure_com_dirs()
    if not os.path.exists(CONFIG_PATH):
        cfg = default_config(available_ports)
        save_config(cfg)
        return cfg

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, ValueError):
        cfg = default_config(available_ports)
        save_config(cfg)
        return cfg

    selected = [str(p).upper() for p in data.get("selected_ports", [])]

    settings = {}
    raw_settings = data.get("port_settings", {})
    for port in set(selected + list(raw_settings.keys())):
        settings[port.upper()] = _settings_from_dict(raw_settings.get(port, {}))

    for port in selected:
        settings.setdefault(port, PortSettings())

    return MonitorConfig(
        selected_ports=selected,
        port_settings=settings,
        driver_backend_enabled=bool(data.get("driver_backend_enabled", False)),
        direct_monitor_enabled=bool(data.get("direct_monitor_enabled", False)),
    )


def save_config(config: MonitorConfig) -> None:
    ensure_com_dirs()
    data = {
        "selected_ports": [p.upper() for p in config.selected_ports],
        "port_settings": {
            p.upper(): asdict(settings)
            for p, settings in config.port_settings.items()
        },
        "driver_backend_enabled": bool(config.driver_backend_enabled),
        "direct_monitor_enabled": bool(config.direct_monitor_enabled),
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)


def parse_hex_patterns(text: str) -> List[bytes]:
    patterns = []
    chunks = re.split(r"[,;\n]+", text or "")
    for chunk in chunks:
        normalized = chunk.strip().replace("0x", "").replace("0X", "")
        normalized = re.sub(r"[^0-9A-Fa-f]", "", normalized)
        if not normalized:
            continue
        if len(normalized) % 2:
            raise ValueError("HEX 패턴 길이가 올바르지 않습니다: {}".format(chunk.strip()))
        patterns.append(bytes.fromhex(" ".join(
            normalized[i:i + 2] for i in range(0, len(normalized), 2)
        )))
    return patterns or list(DEFAULT_CUT_PATTERNS)


def is_com0com_port(port_info) -> bool:
    text = " ".join(str(getattr(port_info, attr, "") or "") for attr in (
        "device", "name", "description", "hwid", "manufacturer", "product",
    )).lower()
    return "com0com" in text or "cnca" in text or "cncb" in text


def list_physical_ports() -> List[str]:
    try:
        from serial.tools import list_ports
    except Exception:
        return []

    ports = []
    for info in list_ports.comports():
        device = str(getattr(info, "device", "") or "").upper()
        if not device.startswith("COM"):
            continue
        if is_com0com_port(info):
            continue
        ports.append(device)
    return sorted(set(ports), key=lambda p: int(p[3:]) if p[3:].isdigit() else 9999)


def serial_kwargs(settings: PortSettings) -> dict:
    kwargs = {
        "baudrate": int(settings.baudrate),
        "bytesize": int(settings.bytesize),
        "parity": str(settings.parity).upper()[:1] or "N",
        "stopbits": float(settings.stopbits),
        "timeout": 0.2,
    }
    flow = (settings.flow_control or "none").lower()
    kwargs["xonxoff"] = flow == "xonxoff"
    kwargs["rtscts"] = flow == "rtscts"
    kwargs["dsrdtr"] = flow == "dsrdtr"
    return kwargs


def _find_earliest_pattern(buffer: bytearray, patterns: List[bytes]) -> Tuple[int, bytes]:
    best_index = -1
    best_pattern = b""
    for pattern in patterns:
        if not pattern:
            continue
        idx = buffer.find(pattern)
        if idx >= 0 and (best_index < 0 or idx < best_index):
            best_index = idx
            best_pattern = pattern
    return best_index, best_pattern


class ReceiptSplitter:
    def __init__(
        self,
        cut_patterns: Optional[List[bytes]] = None,
        idle_timeout_ms: int = 1500,
        min_bytes: int = 8,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self.cut_patterns = cut_patterns or list(DEFAULT_CUT_PATTERNS)
        self.idle_timeout_ms = max(int(idle_timeout_ms), 100)
        self.min_bytes = max(int(min_bytes), 1)
        self.clock = clock or time.monotonic
        self.buffer = bytearray()
        self.last_data_at = None

    def feed(self, data: bytes) -> List[bytes]:
        if not data:
            return []
        self.buffer.extend(data)
        self.last_data_at = self.clock()
        receipts = []
        while True:
            idx, pattern = _find_earliest_pattern(self.buffer, self.cut_patterns)
            if idx < 0:
                break
            end = idx + len(pattern)
            receipt = bytes(self.buffer[:end])
            del self.buffer[:end]
            if len(receipt) >= self.min_bytes:
                receipts.append(receipt)
        return receipts

    def flush_idle(self) -> List[bytes]:
        if not self.buffer or self.last_data_at is None:
            return []
        elapsed_ms = (self.clock() - self.last_data_at) * 1000
        if elapsed_ms < self.idle_timeout_ms or len(self.buffer) < self.min_bytes:
            return []
        receipt = bytes(self.buffer)
        self.buffer.clear()
        self.last_data_at = None
        return [receipt]

    def flush_all(self) -> List[bytes]:
        if not self.buffer:
            return []
        receipt = bytes(self.buffer)
        self.buffer.clear()
        self.last_data_at = None
        return [receipt] if len(receipt) >= self.min_bytes else []


class ReceiptLogWriter:
    def __init__(self, output_dirs: Optional[List[str]] = None) -> None:
        self.output_dirs = output_dirs or [NEWBMLOG_DIR, NEWLOG_DIR]
        for path in self.output_dirs:
            os.makedirs(path, exist_ok=True)

    def _filename(self, port: str, written_at: Optional[datetime]) -> str:
        timestamp = (written_at or datetime.now()).strftime("%Y%m%d%H%M%S")
        safe_port = re.sub(r"[^A-Za-z0-9_]", "", port.upper()) or "COM"
        return "{}_{}.LOG".format(safe_port, timestamp)

    def _unique_paths(self, filename: str) -> List[str]:
        base, ext = os.path.splitext(filename)
        candidate = filename
        seq = 1
        while any(os.path.exists(os.path.join(path, candidate)) for path in self.output_dirs):
            candidate = "{}_{:02d}{}".format(base, seq, ext)
            seq += 1
        return [os.path.join(path, candidate) for path in self.output_dirs]

    def write(self, port: str, data: bytes, written_at: Optional[datetime] = None) -> List[str]:
        filename = self._filename(port, written_at)
        paths = self._unique_paths(filename)
        for path in paths:
            with open(path, "wb") as fp:
                fp.write(data)
        return paths


def preview_text(data: bytes, encoding: str = "cp949") -> str:
    text = data.decode(encoding or "cp949", errors="ignore")
    cleaned = []
    for ch in text:
        if ch in "\r\n\t":
            cleaned.append(ch)
        elif ord(ch) >= 32:
            cleaned.append(ch)
    return "".join(cleaned).replace("\x00", "")
