import configparser
import os
import shutil
from datetime import datetime

from constants import BAUD_RATE, PRINT_PORT


def _backup(ini_path: str) -> None:
    if not os.path.exists(ini_path):
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(ini_path, ini_path + ".bak_{}".format(ts))


def _make_parser() -> configparser.RawConfigParser:
    cfg = configparser.RawConfigParser()
    cfg.optionxform = str  # 키 대소문자 보존
    return cfg


def _read_ini(cfg: configparser.RawConfigParser, ini_path: str) -> None:
    if os.path.exists(ini_path):
        try:
            cfg.read(ini_path, encoding="cp949")
        except Exception:
            cfg.read(ini_path, encoding="utf-8")


def _write_ini(cfg: configparser.RawConfigParser, ini_path: str) -> None:
    ini_dir = os.path.dirname(ini_path)
    if ini_dir:
        os.makedirs(ini_dir, exist_ok=True)
    with open(ini_path, "w", encoding="cp949") as f:
        cfg.write(f, space_around_delimiters=False)


def write_moaline_plus_ini(ini_path: str, port_a: str, port_b: str) -> None:
    """
    모아라인 플러스 LinkAge.ini 에 연동 설정 추가.
    기존 내용은 유지하며 [linkage] 섹션에 키만 추가/갱신.
    """
    _backup(ini_path)
    cfg = _make_parser()
    _read_ini(cfg, ini_path)

    if not cfg.has_section("linkage"):
        cfg.add_section("linkage")

    managed_keys = {"PRNYN", "PRINT1", "POS1", "MOA1", "BaudRate1"}
    extra_options = []
    for key, value in cfg.items("linkage"):
        if key not in managed_keys:
            extra_options.append((key, value))

    for key in managed_keys:
        cfg.remove_option("linkage", key)

    cfg.set("linkage", "PRNYN", "1")
    cfg.set("linkage", "PRINT1", "선택")
    cfg.set("linkage", "POS1", port_a)
    cfg.set("linkage", "MOA1", port_b)
    cfg.set("linkage", "BaudRate1", BAUD_RATE)
    for key, value in extra_options:
        cfg.set("linkage", key, value)

    _write_ini(cfg, ini_path)


def write_moaline_store_ini(ini_path: str, port_a: str, port_b: str) -> None:
    """
    모아라인 상점 Call Star.ini 에 연동 설정 추가.
    [linkage] 섹션과 [linkCOM99] 섹션을 추가/갱신.
    """
    _backup(ini_path)
    cfg = _make_parser()
    _read_ini(cfg, ini_path)

    if not cfg.has_section("linkage"):
        cfg.add_section("linkage")

    cfg.set("linkage", "PRINT1", PRINT_PORT)
    cfg.set("linkage", "POS1", port_a)
    cfg.set("linkage", "MOA1", port_b)
    cfg.set("linkage", "POS2", "")
    cfg.set("linkage", "MOA2", "")

    baud_section = f"link{PRINT_PORT}"
    if not cfg.has_section(baud_section):
        cfg.add_section(baud_section)
    cfg.set(baud_section, "Settings", f"{BAUD_RATE},n,8,1")

    _write_ini(cfg, ini_path)


def read_linkage_settings(ini_path: str) -> dict:
    """현재 INI 파일의 [linkage] 연동 설정을 읽어 대문자 값으로 반환."""
    cfg = _make_parser()
    _read_ini(cfg, ini_path)

    if not cfg.has_section("linkage"):
        return {}

    settings = {}
    for key in ("PRNYN", "PRINT1", "POS1", "MOA1", "BaudRate1"):
        if cfg.has_option("linkage", key):
            settings[key] = cfg.get("linkage", key).strip().upper()

    print_port = settings.get("PRINT1", PRINT_PORT)
    baud_sections = ["link{}".format(print_port)]
    fallback_section = "link{}".format(PRINT_PORT)
    if fallback_section not in baud_sections:
        baud_sections.append(fallback_section)

    for baud_section in baud_sections:
        if cfg.has_section(baud_section) and cfg.has_option(baud_section, "Settings"):
            settings["Settings"] = cfg.get(baud_section, "Settings").strip().upper()
            break
    return settings


def create_moaline_plus_dirs(install_dir: str) -> None:
    """모아라인 플러스 COM 로그 폴더 생성."""
    from constants import MOALINE_PLUS_COM_DIRS
    for rel_dir in MOALINE_PLUS_COM_DIRS:
        os.makedirs(os.path.join(install_dir, rel_dir), exist_ok=True)


def restore_from_backup(ini_path: str) -> bool:
    """
    가장 최근 백업 파일로 복원. 성공 시 True.
    백업이 없으면 False 반환.
    """
    import glob
    pattern = ini_path + ".bak_*"
    backups = sorted(glob.glob(pattern))
    if not backups:
        return False
    latest = backups[-1]
    shutil.copy2(latest, ini_path)
    return True


def remove_linkage_keys(ini_path: str) -> None:
    """
    INI 파일에서 연동 설정 키 제거 (백업 없을 때 fallback).
    모아라인 플러스: [linkage]의 PRINT1/POS1/MOA1/BaudRate1 삭제
    모아라인 상점:   [linkage] 섹션과 [linkCOM99] 섹션 전체 삭제
    """
    from constants import PRINT_PORT
    cfg = _make_parser()
    _read_ini(cfg, ini_path)

    print_port = PRINT_PORT
    if cfg.has_section("linkage") and cfg.has_option("linkage", "PRINT1"):
        print_port = cfg.get("linkage", "PRINT1").strip().upper() or PRINT_PORT

    for key in ("PRNYN", "PRINT1", "POS1", "MOA1", "BaudRate1", "POS2", "MOA2"):
        if cfg.has_section("linkage"):
            cfg.remove_option("linkage", key)

    for baud_section in {"link{}".format(PRINT_PORT), "link{}".format(print_port)}:
        if cfg.has_section(baud_section):
            cfg.remove_section(baud_section)

    _write_ini(cfg, ini_path)


def restore_ini(ini_path: str) -> str:
    """
    백업 복원 시도 → 없으면 키 제거.
    반환값: 수행한 작업 설명 문자열.
    """
    if restore_from_backup(ini_path):
        return "백업에서 복원 완료"
    remove_linkage_keys(ini_path)
    return "연동 키 제거 완료 (백업 없음)"
