import os
import sys
import tempfile
import time
from datetime import datetime


APP_LOG_DIR_NAME = "MoalineLinkage"
_START_TIME = time.perf_counter()


def _log_dir() -> str:
    base_dir = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    log_dir = os.path.join(base_dir, APP_LOG_DIR_NAME, "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        return log_dir
    except OSError:
        fallback = os.path.join(tempfile.gettempdir(), APP_LOG_DIR_NAME, "logs")
        os.makedirs(fallback, exist_ok=True)
        return fallback


def get_log_path() -> str:
    filename = "startup_{}.log".format(datetime.now().strftime("%Y%m%d"))
    return os.path.join(_log_dir(), filename)


def log_startup_event(event: str, detail: str = "") -> None:
    elapsed = time.perf_counter() - _START_TIME
    line = "{time} +{elapsed:0.3f}s {event}{detail}\n".format(
        time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        elapsed=elapsed,
        event=event,
        detail=" | " + detail if detail else "",
    )
    try:
        with open(get_log_path(), "a", encoding="utf-8") as fp:
            fp.write(line)
    except OSError:
        pass


def log_runtime_context() -> None:
    parts = [
        "exe={}".format(sys.executable),
        "argv={}".format(" ".join(sys.argv)),
        "cwd={}".format(os.getcwd()),
        "frozen={}".format(bool(getattr(sys, "frozen", False))),
        "meipass={}".format(getattr(sys, "_MEIPASS", "")),
    ]
    log_startup_event("runtime_context", " | ".join(parts))
