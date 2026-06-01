COM0COM_DOWNLOAD_URL = (
    "https://twds.dl.sourceforge.net/project/com0com/com0com/3.0.0.0/"
    "com0com-3.0.0.0-i386-and-x64-signed.zip?viasf=1&fid=56a10db795a35994"
)
COM0COM_INSTALLER_X64 = "Setup_com0com_v3.0.0.0_W7_x64_signed.exe"
COM0COM_INSTALLER_X86 = "Setup_com0com_v3.0.0.0_W7_x86_signed.exe"
COM0COM_ZIP_DEST = r"C:\com0com_setup.zip"
COM0COM_EXTRACT_DIR = r"C:\com0com_tmp"

COM0COM_REG_KEYS = [
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\com0com",
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\com0com",
]

DEFAULT_PORT_A = "COM16"
DEFAULT_PORT_B = "COM15"
PORT_SEARCH_RANGE = range(20, 41)

MOALINE_PLUS_DEFAULT_DIR = r"C:\Moacall_Plus"
MOALINE_PLUS_ALT_DIR = r"C:\MOALINE_PLUS"
MOALINE_PLUS_EXE = "moacall_plus.exe"
MOALINE_PLUS_INI = "LinkAge.ini"
MOALINE_PLUS_COM_DIRS = [r"COM\NEWBMLOG", r"COM\NEWLOG"]

MOALINE_STORE_DEFAULT_DIR = r"C:\Program Files (x86)\moacall"
MOALINE_STORE_EXE = "moacall.exe"
MOALINE_STORE_INI = "Call Star.ini"

PRINT_PORT = "COM99"
BAUD_RATE = "9600"

SUPPORT_URL = "https://barogo-official.channel.io/workflows/830603"
