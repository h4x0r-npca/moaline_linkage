import ctypes
import sys


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> None:
    """현재 프로세스를 관리자 권한으로 재실행."""
    script = sys.executable
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", script, params, None, 1)
    sys.exit(0)


def ensure_admin() -> None:
    """관리자 권한이 없으면 재실행 요청."""
    if not is_admin():
        relaunch_as_admin()
