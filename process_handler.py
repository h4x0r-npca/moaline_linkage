import os
import subprocess
import time

import psutil


def kill_by_name(exe_name: str) -> bool:
    """주어진 이름의 프로세스를 모두 종료. 종료된 프로세스가 있으면 True 반환."""
    killed = False
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info["name"].lower() == exe_name.lower():
                proc.kill()
                proc.wait(timeout=5)
                killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return killed


def start_program(exe_path: str) -> bool:
    """프로그램을 비동기로 실행. 성공 시 True 반환."""
    try:
        subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
        return True
    except Exception:
        return False


def restart_program(exe_name: str, exe_path: str) -> None:
    """프로그램 종료 후 재시작."""
    kill_by_name(exe_name)
    time.sleep(1.5)
    start_program(exe_path)
