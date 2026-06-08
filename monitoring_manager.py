import os
import shutil
import subprocess
import time
import winreg
from typing import Callable, Optional

import psutil

from serial_monitor_core import COM_ROOT, NEWBMLOG_DIR, NEWLOG_DIR


AGENT_EXE_NAME = "moa_linkageSM.exe"
RUN_VALUE_NAME = "MoalineLinkageSM"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def agent_install_path() -> str:
    return os.path.join(COM_ROOT, AGENT_EXE_NAME)


def ensure_monitoring_dirs() -> None:
    for path in (COM_ROOT, NEWBMLOG_DIR, NEWLOG_DIR):
        os.makedirs(path, exist_ok=True)


def is_agent_running() -> bool:
    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").lower() == AGENT_EXE_NAME.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def stop_agent() -> bool:
    stopped = False
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if (proc.info.get("name") or "").lower() == AGENT_EXE_NAME.lower():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                stopped = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return stopped


def start_agent() -> bool:
    exe_path = agent_install_path()
    if not os.path.exists(exe_path):
        return False
    try:
        subprocess.Popen([exe_path], cwd=COM_ROOT, close_fds=True)
        time.sleep(1)
        return True
    except Exception:
        return False


def find_agent_source(resource_path_func: Callable[[str], str]) -> Optional[str]:
    candidates = [
        resource_path_func(AGENT_EXE_NAME),
        os.path.join(os.getcwd(), "dist", AGENT_EXE_NAME),
        os.path.join(os.getcwd(), AGENT_EXE_NAME),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def copy_agent(source_path: str) -> str:
    ensure_monitoring_dirs()
    target_path = agent_install_path()
    if os.path.abspath(source_path).lower() != os.path.abspath(target_path).lower():
        shutil.copy2(source_path, target_path)
    return target_path


def _open_run_key(root, access):
    flags = [access]
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        flags.insert(0, access | winreg.KEY_WOW64_64KEY)
    last_error = None
    for flag in flags:
        try:
            return winreg.OpenKey(root, RUN_KEY, 0, flag)
        except OSError as exc:
            last_error = exc
    raise last_error


def register_run(exe_path: str) -> str:
    command = '"{}"'.format(exe_path)
    for root, label in ((winreg.HKEY_LOCAL_MACHINE, "HKLM"), (winreg.HKEY_CURRENT_USER, "HKCU")):
        try:
            with _open_run_key(root, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, command)
            return label
        except OSError:
            continue
    raise RuntimeError("자동실행 등록에 실패했습니다.")


def unregister_run() -> None:
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with _open_run_key(root, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, RUN_VALUE_NAME)
                except FileNotFoundError:
                    pass
        except OSError:
            pass


def remove_agent_file() -> bool:
    path = agent_install_path()
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True


def monitoring_status_text() -> tuple:
    if is_agent_running():
        return True, "STATUS : 연동 완료"
    return False, "STATUS : 연동 미설치"
