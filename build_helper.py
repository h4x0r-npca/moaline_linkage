import subprocess
import sys
from datetime import date
from pathlib import Path


def install_package(*args):
    subprocess.run([sys.executable, "-m", "pip", "install"] + list(args), check=True)


# psutil: 컴파일 없이 미리 빌드된 wheel만 사용
install_package("psutil==5.9.5", "--only-binary", ":all:", "--quiet")

install_package("Pillow==10.4.0", "--only-binary", ":all:", "--quiet")

install_package("customtkinter==5.2.2", "--quiet")

install_package("pyserial==3.5", "--quiet")

install_package("pystray==0.19.5", "--quiet")

install_package("pyinstaller==4.5.1", "--quiet")

Path("build_info.py").write_text(
    'APP_VERSION = "1.0"\nRELEASE_DATE = "{}"\n'.format(date.today().isoformat()),
    encoding="utf-8",
)

import PyInstaller.__main__
PyInstaller.__main__.run([
    "moa_linkage_sm.py",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--noconsole",
    "--noupx",
    "--icon", "moaline.ico",
    "--collect-data", "customtkinter",
    "--add-data", "로고.webp;.",
    "--add-data", "로고한글.webp;.",
    "--add-data", "moaline.ico;.",
    "--name", "moa_linkageSM",
])

PyInstaller.__main__.run([
    "main.py",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--noconsole",
    "--noupx",
    "--uac-admin",
    "--icon", "moaline.ico",
    "--version-file", "version_info.txt",
    "--collect-data", "customtkinter",
    "--add-data", "로고.webp;.",
    "--add-data", "로고한글.webp;.",
    "--add-data", "로고.svg;.",
    "--add-data", "moaline.ico;.",
    "--add-binary", "dist\\moa_linkageSM.exe;.",
    "--name", "모아라인연동자동화",
])

dist_dir = Path("dist")
target_exe = dist_dir / "모아라인연동자동화.exe"
temp_exe = dist_dir / "모아라인연동자동화_temp.exe"

if temp_exe.exists():
    temp_exe.replace(target_exe)
