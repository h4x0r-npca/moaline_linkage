import os
import winreg
from dataclasses import dataclass
from typing import List, Optional

from constants import (
    MOALINE_PLUS_ALT_DIR,
    MOALINE_PLUS_DEFAULT_DIR,
    MOALINE_PLUS_EXE,
    MOALINE_PLUS_INI,
    MOALINE_STORE_DEFAULT_DIR,
    MOALINE_STORE_EXE,
    MOALINE_STORE_INI,
)

UNINSTALL_PATHS = [
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]


@dataclass
class MoalineInstall:
    kind: str        # "plus" 또는 "store"
    display_name: str
    install_dir: str
    exe_path: str
    ini_path: str


def _iter_uninstall_entries() -> List[dict]:
    seen_keys = set()
    entries = []
    for hive, path in UNINSTALL_PATHS:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(root, i)
                i += 1
            except OSError:
                break
            if subkey_name in seen_keys:
                continue
            seen_keys.add(subkey_name)
            try:
                sub = winreg.OpenKey(root, subkey_name)
                try:
                    display = winreg.QueryValueEx(sub, "DisplayName")[0]
                except OSError:
                    winreg.CloseKey(sub)
                    continue
                try:
                    location = winreg.QueryValueEx(sub, "InstallLocation")[0]
                except OSError:
                    location = ""
                winreg.CloseKey(sub)
                entries.append({
                    "key": subkey_name,
                    "display": display,
                    "location": location.strip().rstrip("\\"),
                })
            except OSError:
                continue
        winreg.CloseKey(root)
    return entries


def _resolve_dir(location: str, *fallbacks: str) -> Optional[str]:
    """InstallLocation 또는 fallback 경로 중 존재하는 첫 번째 반환."""
    for candidate in [location] + list(fallbacks):
        if candidate and os.path.isdir(candidate):
            return candidate
    return None


def detect_moaline() -> List[MoalineInstall]:
    """
    레지스트리에서 모아라인 플러스/상점 설치 정보 탐지.
    반환값: Plus 우선 정렬된 목록.
    """
    entries = _iter_uninstall_entries()
    found = []

    for entry in entries:
        display = entry["display"]
        location = entry["location"]

        # 모아라인 플러스
        if "모아콜플러스" in display or "MOALINE_PLUS" in display.upper() or "모아라인플러스" in display:
            install_dir = _resolve_dir(
                location, MOALINE_PLUS_DEFAULT_DIR, MOALINE_PLUS_ALT_DIR
            )
            if install_dir is None:
                continue
            exe = os.path.join(install_dir, MOALINE_PLUS_EXE)
            ini = os.path.join(install_dir, MOALINE_PLUS_INI)
            if os.path.exists(exe):
                found.append(MoalineInstall(
                    kind="plus",
                    display_name=display,
                    install_dir=install_dir,
                    exe_path=exe,
                    ini_path=ini,
                ))

        # 모아라인 상점
        elif ("모아콜 가맹점" in display or "모아라인 상점" in display
              or entry["key"].lower() == "moacall"):
            install_dir = _resolve_dir(location, MOALINE_STORE_DEFAULT_DIR)
            if install_dir is None:
                continue
            exe = os.path.join(install_dir, MOALINE_STORE_EXE)
            ini = os.path.join(install_dir, MOALINE_STORE_INI)
            if os.path.exists(exe):
                found.append(MoalineInstall(
                    kind="store",
                    display_name=display,
                    install_dir=install_dir,
                    exe_path=exe,
                    ini_path=ini,
                ))

    # 중복 제거 (kind 기준)
    seen = set()
    unique = []
    for item in found:
        if item.kind not in seen:
            seen.add(item.kind)
            unique.append(item)

    # Plus 우선 정렬
    unique.sort(key=lambda x: 0 if x.kind == "plus" else 1)
    return unique
