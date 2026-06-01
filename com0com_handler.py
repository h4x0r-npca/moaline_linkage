import os
import shutil
import subprocess
import time
import urllib.request
import winreg
import zipfile
from typing import Callable, List, Optional, Tuple

# GUI 앱에서 콘솔 창 없이 서브프로세스 실행
_NO_WINDOW = subprocess.CREATE_NO_WINDOW


def _run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    """콘솔 없는 환경에서도 안전하게 subprocess 실행."""
    return subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=_NO_WINDOW,
        **kwargs,
    )

from constants import (
    COM0COM_DOWNLOAD_URL,
    COM0COM_EXTRACT_DIR,
    COM0COM_INSTALLER_X64,
    COM0COM_INSTALLER_X86,
    COM0COM_REG_KEYS,
    COM0COM_ZIP_DEST,
    DEFAULT_PORT_A,
    DEFAULT_PORT_B,
    PORT_SEARCH_RANGE,
)


def get_install_location() -> Optional[str]:
    """레지스트리에서 com0com 설치 경로를 반환. 미설치 시 None."""
    for reg_key in COM0COM_REG_KEYS:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_key)
            location, _ = winreg.QueryValueEx(key, "InstallLocation")
            winreg.CloseKey(key)
            location = location.rstrip("\\").strip()
            if location and os.path.isdir(location):
                return location
        except (FileNotFoundError, OSError):
            continue
    return None


def is_installed() -> bool:
    return get_install_location() is not None


def get_setupc_path(install_location: str) -> str:
    return os.path.join(install_location, "setupc.exe")


def download_zip(progress_cb: Optional[Callable[[int], None]] = None) -> None:
    """com0com ZIP 파일 다운로드."""
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    urllib.request.install_opener(opener)

    def reporthook(count: int, block_size: int, total_size: int) -> None:
        if progress_cb and total_size > 0:
            pct = min(int(count * block_size * 100 / total_size), 100)
            progress_cb(pct)

    urllib.request.urlretrieve(COM0COM_DOWNLOAD_URL, COM0COM_ZIP_DEST, reporthook)


def extract_zip() -> None:
    """ZIP 파일 압축 해제."""
    os.makedirs(COM0COM_EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(COM0COM_ZIP_DEST, "r") as z:
        z.extractall(COM0COM_EXTRACT_DIR)
    os.remove(COM0COM_ZIP_DEST)


def _os_is_64bit() -> bool:
    """32-bit Python이 64-bit OS에서 실행될 때도 올바르게 판별."""
    # PROCESSOR_ARCHITEW6432 는 WOW64(32-bit 프로세스 + 64-bit OS) 환경에서만 존재
    if os.environ.get("PROCESSOR_ARCHITEW6432", "").upper() == "AMD64":
        return True
    return os.environ.get("PROCESSOR_ARCHITECTURE", "").upper() == "AMD64"


def install_driver() -> bool:
    """OS 아키텍처에 맞는 설치 파일 실행 (무음 설치)."""
    if _os_is_64bit():
        installer_name = COM0COM_INSTALLER_X64
    else:
        installer_name = COM0COM_INSTALLER_X86

    installer_path = os.path.join(COM0COM_EXTRACT_DIR, installer_name)
    if not os.path.exists(installer_path):
        raise FileNotFoundError(f"설치 파일을 찾을 수 없습니다: {installer_path}")

    result = _run([installer_path, "/S"], timeout=180)
    time.sleep(4)

    try:
        shutil.rmtree(COM0COM_EXTRACT_DIR, ignore_errors=True)
    except Exception:
        pass

    return result.returncode == 0


def get_busy_ports(setupc_path: str) -> List[str]:
    """현재 사용 중인 COM 포트 목록 반환."""
    try:
        cwd = os.path.dirname(setupc_path)
        result = _run([setupc_path, "busynames", "COM*"], timeout=30, cwd=cwd)
        output = result.stdout.decode("utf-8", errors="ignore")
        ports = []
        for line in output.splitlines():
            line = line.strip()
            if line.upper().startswith("COM"):
                ports.append(line.upper())
        return ports
    except Exception:
        return []


def find_available_port_pair(setupc_path: str) -> Tuple[str, str]:
    """사용 가능한 COM 포트 쌍 자동 탐색. 기본값 COM16/COM15 우선."""
    busy = get_busy_ports(setupc_path)
    busy_upper = [p.upper() for p in busy]

    if DEFAULT_PORT_A not in busy_upper and DEFAULT_PORT_B not in busy_upper:
        return DEFAULT_PORT_A, DEFAULT_PORT_B

    for n in PORT_SEARCH_RANGE:
        a = f"COM{n}"
        b = f"COM{n + 1}"
        if a not in busy_upper and b not in busy_upper:
            return a, b

    raise RuntimeError("사용 가능한 COM 포트 쌍을 찾을 수 없습니다 (COM20~COM40 모두 사용 중).")


def find_low_available_port_pair(setupc_path: str) -> Tuple[str, str]:
    """COM1부터 순서대로 비어 있는 포트 2개를 찾아 반환."""
    busy_upper = {p.upper() for p in get_busy_ports(setupc_path)}
    for pair in get_port_pairs(setupc_path):
        busy_upper.add(pair["port_a"].upper())
        busy_upper.add(pair["port_b"].upper())

    available = []
    for n in range(1, 100):
        port = "COM{}".format(n)
        if port not in busy_upper:
            available.append(port)
            if len(available) == 2:
                return available[0], available[1]

    raise RuntimeError("사용 가능한 낮은 COM 포트 쌍을 찾을 수 없습니다 (COM1~COM99 모두 사용 중).")


def create_virtual_ports(setupc_path: str, port_a: str, port_b: str) -> None:
    """가상 COM 포트 쌍 생성."""
    cwd = os.path.dirname(setupc_path)
    result = _run(
        [setupc_path, "--wait", "30", "install",
         "PortName={}".format(port_a), "PortName={}".format(port_b)],
        timeout=60,
        cwd=cwd,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout).decode("utf-8", errors="ignore").strip()
        raise RuntimeError("포트 생성 실패: {}".format(err))


def get_port_pairs(setupc_path: str) -> List[dict]:
    """
    com0com 가상 포트 쌍 목록 반환.
    반환값: [{"index": 0, "port_a": "COM16", "port_b": "COM15"}, ...]
    """
    cwd = os.path.dirname(setupc_path)
    try:
        result = _run([setupc_path, "list"], timeout=30, cwd=cwd)
        output = result.stdout.decode("utf-8", errors="ignore")
    except Exception:
        return []

    pairs = []
    pair_map = {}
    current_idx = None
    current_ports = []

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if parts:
            device_name = parts[0].upper()
            if device_name.startswith("CNCA") or device_name.startswith("CNCB"):
                idx_text = device_name[4:]
                if idx_text.isdigit():
                    pair = pair_map.setdefault(
                        int(idx_text),
                        {"index": int(idx_text), "port_a": "", "port_b": ""},
                    )
                    for part in parts[1:]:
                        if part.upper().startswith("PORTNAME="):
                            port_name = part.split("=", 1)[1].upper()
                            if device_name.startswith("CNCA"):
                                pair["port_a"] = port_name
                            else:
                                pair["port_b"] = port_name
                    continue

        # 숫자로 시작하는 줄 = 새 쌍의 시작
        if parts and parts[0].isdigit():
            if current_idx is not None and len(current_ports) >= 2:
                pairs.append({"index": current_idx,
                               "port_a": current_ports[0],
                               "port_b": current_ports[1]})
            current_idx = int(parts[0])
            current_ports = []
            for part in parts[1:]:
                if part.upper().startswith("PORTNAME="):
                    current_ports.append(part.split("=", 1)[1].upper())
        else:
            for part in parts:
                if part.upper().startswith("PORTNAME="):
                    current_ports.append(part.split("=", 1)[1].upper())

    if current_idx is not None and len(current_ports) >= 2:
        pairs.append({"index": current_idx,
                       "port_a": current_ports[0],
                       "port_b": current_ports[1]})

    for idx in sorted(pair_map):
        pair = pair_map[idx]
        if pair["port_a"] and pair["port_b"]:
            pairs.append(pair)
    return pairs


def remove_port_pair(setupc_path: str, pair_index: int) -> None:
    """com0com 포트 쌍 제거."""
    cwd = os.path.dirname(setupc_path)
    result = _run(
        [setupc_path, "--wait", "30", "remove", str(pair_index)],
        timeout=60,
        cwd=cwd,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout).decode("utf-8", errors="ignore").strip()
        raise RuntimeError("포트 제거 실패: {}".format(err))


def remove_ports_by_name(setupc_path: str, port_a: str, port_b: str) -> bool:
    """
    port_a 또는 port_b 가 포함된 쌍을 찾아 제거.
    제거된 쌍이 있으면 True 반환.
    """
    targets = {port_a.upper(), port_b.upper()}
    pairs = get_port_pairs(setupc_path)
    removed = False
    # 인덱스 역순으로 제거해야 이후 인덱스가 밀리지 않음
    for pair in sorted(pairs, key=lambda p: p["index"], reverse=True):
        if pair["port_a"] in targets or pair["port_b"] in targets:
            remove_port_pair(setupc_path, pair["index"])
            removed = True
    return removed
