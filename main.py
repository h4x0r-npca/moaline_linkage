import os
import sys
import threading
import tkinter as tk
import ctypes
import time
import webbrowser
from tkinter import scrolledtext
from typing import List, Tuple

import startup_logger

startup_logger.log_startup_event("python_start")
startup_logger.log_runtime_context()


ERROR_ALREADY_EXISTS = 183
ERROR_ACCESS_DENIED = 5
_INSTANCE_MUTEX_HANDLE = None


def acquire_single_instance() -> bool:
    global _INSTANCE_MUTEX_HANDLE
    mutex_name = "Local\\MoalineLinkageAutomation"
    ctypes.windll.kernel32.SetLastError(0)
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    if not handle and last_error != ERROR_ACCESS_DENIED:
        startup_logger.log_startup_event(
            "single_instance_unavailable",
            "last_error={}".format(last_error),
        )
        return True
    if not handle and last_error == ERROR_ACCESS_DENIED:
        startup_logger.log_startup_event("duplicate_instance", "mutex access denied")
        return False
    if last_error == ERROR_ALREADY_EXISTS:
        startup_logger.log_startup_event("duplicate_instance", "mutex already exists")
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
        return False
    _INSTANCE_MUTEX_HANDLE = handle
    startup_logger.log_startup_event("single_instance_acquired")
    return True


if not acquire_single_instance():
    sys.exit(0)

import customtkinter as ctk
from PIL import Image, ImageTk

import admin
import com0com_handler as c0c
import config_writer
import moaline_detector
import process_handler
from build_info import APP_VERSION, RELEASE_DATE
from constants import BAUD_RATE, DEFAULT_PORT_A, DEFAULT_PORT_B, SUPPORT_URL


def resource_path(relative_path: str) -> str:
    """Return the correct resource path for source runs and PyInstaller exe runs."""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def _is_com_port(value: str) -> bool:
    value = value.strip().upper()
    return value.startswith("COM") and value[3:].isdigit()

# ──────────────────────────────────────────────
# 단계 정의
# ──────────────────────────────────────────────
INSTALL_STEPS = [
    "com0com 설치 확인",
    "가상 COM 포트 생성",
    "모아라인 프로그램 감지",
    "설정 파일 수정",
    "폴더 생성",
    "모아라인 재시작",
]

REMOVE_STEPS = [
    "모아라인 프로그램 감지",
    "설정 파일 복원",
    "가상 COM 포트 제거",
    "모아라인 재시작",
    "",
    "",
]

MAX_STEPS = 6

STATUS_WAIT = "○"
STATUS_RUN  = "●"
STATUS_OK   = "✓"
STATUS_ERR  = "!"

COLOR_PRIMARY = "#570DCA"
COLOR_PRIMARY_DARK = "#4700A8"
COLOR_PRIMARY_SOFT = "#F3ECFF"
COLOR_PRIMARY_LINE = "#D7C4FF"
COLOR_TEXT = "#191124"
COLOR_MUTED = "#70677D"
COLOR_WAIT  = "#A59BAF"
COLOR_RUN   = COLOR_PRIMARY
COLOR_OK    = "#139E66"
COLOR_ERR   = "#D92D20"
COLOR_WARN  = "#B7791F"
COLOR_BG    = "#F7F4FB"
COLOR_PANEL = "#FFFFFF"
COLOR_LOG_BG = "#17131F"

FONT_FAMILY = "맑은 고딕"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


# ──────────────────────────────────────────────
# 공통 다이얼로그 헬퍼
# ──────────────────────────────────────────────
def _center_on(dlg: tk.Toplevel, parent: tk.Tk) -> None:
    dlg.update_idletasks()
    pw = parent.winfo_x() + parent.winfo_width() // 2
    ph = parent.winfo_y() + parent.winfo_height() // 2
    w, h = dlg.winfo_width(), dlg.winfo_height()
    dlg.geometry("+{}+{}".format(pw - w // 2, ph - h // 2))


# ──────────────────────────────────────────────
# 연동 완료 다이얼로그 (5번 클릭 / 즉시 닫기)
# ──────────────────────────────────────────────
class CompletionDialog(ctk.CTkToplevel):
    def __init__(self, parent: tk.Tk, port_a: str) -> None:
        super().__init__(parent)
        self.title("연동 완료")
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=COLOR_PANEL)

        msg = (
            "연동 완료되었습니다.\n\n"
            "연동하실 프로그램에 프린터를 추가하신 뒤 {} 으로 잡아주세요.\n"
            "영수증 출력이 되면 자동으로 연동이 됩니다."
        ).format(port_a)

        ctk.CTkLabel(
            self,
            text="연동 완료",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=COLOR_PRIMARY,
        ).pack(padx=28, pady=(24, 8), anchor="w")

        ctk.CTkLabel(
            self, text=msg, justify="left", wraplength=380,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLOR_TEXT,
        ).pack(fill="both", padx=28, pady=(0, 20))

        ctk.CTkButton(
            self, text="확인", width=120, height=36,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_DARK,
            command=self.destroy,
        ).pack(pady=(0, 22))

        _center_on(self, parent)


# ──────────────────────────────────────────────
# 연동 제거 완료 다이얼로그 (5번 클릭 / 즉시 닫기)
# ──────────────────────────────────────────────
class RemoveCompletionDialog(ctk.CTkToplevel):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("연동 제거 완료")
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=COLOR_PANEL)

        ctk.CTkLabel(
            self,
            text="연동 제거 완료",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=COLOR_PRIMARY,
        ).pack(padx=28, pady=(24, 8), anchor="w")

        ctk.CTkLabel(
            self,
            text="연동이 제거되었습니다.\n\n설정 파일이 복원되고 가상 COM 포트가 삭제되었습니다.",
            justify="left", wraplength=360,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLOR_TEXT,
        ).pack(fill="both", padx=28, pady=(0, 20))

        ctk.CTkButton(
            self, text="확인", width=120, height=36,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_DARK,
            command=self.destroy,
        ).pack(pady=(0, 22))

        _center_on(self, parent)


# ──────────────────────────────────────────────
# 오류 다이얼로그
# ──────────────────────────────────────────────
def show_error_and_exit(parent: tk.Tk) -> None:
    dlg = ctk.CTkToplevel(parent)
    dlg.title("오류")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(fg_color=COLOR_PANEL)

    ctk.CTkLabel(
        dlg, text="연동이 되지 않았습니다.\n고객센터로 문의주세요.",
        justify="center",
        font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
        text_color=COLOR_ERR,
    ).pack(padx=34, pady=(28, 18))

    def on_confirm() -> None:
        dlg.destroy()
        webbrowser.open(SUPPORT_URL)
        parent.destroy()

    ctk.CTkButton(
        dlg, text="확인", width=120, height=36,
        font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_DARK,
        command=on_confirm,
    ).pack(pady=(0, 24))

    _center_on(dlg, parent)


# ──────────────────────────────────────────────
# 메인 앱
# ──────────────────────────────────────────────
class App:
    def __init__(self, root: tk.Tk) -> None:
        startup_logger.log_startup_event("app_init_start")
        self.root = root
        root.title(
            "모아라인 연동 자동화 Ver {} (Release : {})".format(
                APP_VERSION,
                RELEASE_DATE,
            )
        )
        root.geometry("820x620")
        root.resizable(False, False)
        root.configure(fg_color=COLOR_BG)
        root.grid_rowconfigure(0, weight=0)
        root.grid_rowconfigure(1, weight=1)
        root.grid_rowconfigure(2, weight=0)
        root.grid_columnconfigure(0, weight=1)

        self._step_labels = []   # (icon_lbl, text_lbl) 튜플 목록
        self._step_rows = []     # row Frame 목록 (숨기기용)
        self._status_refresh_id = 0
        self._low_port_var = ctk.BooleanVar(value=False)
        self._use_low_ports = False
        self._logo_image = self._load_logo("로고한글.webp", (220, 84))
        self._set_window_icon()
        self._build_ui()
        startup_logger.log_startup_event("app_ui_ready")
        self.root.after(300, self._refresh_status)

    def _load_logo(self, filename: str, size: Tuple[int, int]) -> ctk.CTkImage:
        image = Image.open(resource_path(filename))
        return ctk.CTkImage(light_image=image, dark_image=image, size=size)

    def _set_window_icon(self) -> None:
        icon_path = resource_path("moaline.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)
            return

        image = Image.open(resource_path("로고.webp")).resize((64, 64))
        self._icon_photo = ImageTk.PhotoImage(image)
        self.root.iconphoto(True, self._icon_photo)

    # ── UI 구성 ──────────────────────────────
    def _build_ui(self) -> None:
        header = ctk.CTkFrame(
            self.root, fg_color=COLOR_PRIMARY, corner_radius=0, height=124
        )
        header.grid(row=0, column=0, sticky="ew")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="", image=self._logo_image).pack(
            side="left", padx=(26, 18), pady=18
        )

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True, pady=18)

        ctk.CTkLabel(
            title_box, text="연동 자동화",
            font=ctk.CTkFont(family=FONT_FAMILY, size=24, weight="bold"),
            text_color="#FFFFFF",
        ).pack(anchor="w", pady=(12, 2))

        ctk.CTkLabel(
            title_box, text="가상 COM 포트 설정부터 모아라인 재시작까지 한 번에 처리합니다.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color="#EEE4FF",
        ).pack(anchor="w")

        content = ctk.CTkFrame(self.root, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=18)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)

        # 왼쪽: 단계 목록
        step_frame = ctk.CTkFrame(
            content, fg_color=COLOR_PANEL, corner_radius=14,
            border_width=1, border_color=COLOR_PRIMARY_LINE,
            width=220,
        )
        step_frame.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        step_frame.pack_propagate(False)

        ctk.CTkLabel(
            step_frame, text="진행 단계",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(fill="x", padx=16, pady=(18, 10), anchor="w")

        for i in range(MAX_STEPS):
            row = ctk.CTkFrame(step_frame, fg_color="transparent", corner_radius=10)
            row.pack(fill="x", padx=10, pady=3)

            icon_lbl = ctk.CTkLabel(
                row, text=STATUS_WAIT, width=2,
                font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
                text_color=COLOR_WAIT,
            )
            icon_lbl.pack(side="left", padx=(8, 6), pady=7)

            text_lbl = ctk.CTkLabel(
                row, text=INSTALL_STEPS[i], anchor="w",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=COLOR_WAIT,
                wraplength=150,
            )
            text_lbl.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=7)

            self._step_labels.append((icon_lbl, text_lbl))
            self._step_rows.append(row)

        # 오른쪽: 로그 영역
        log_frame = ctk.CTkFrame(
            content, fg_color=COLOR_PANEL, corner_radius=14,
            border_width=1, border_color=COLOR_PRIMARY_LINE,
        )
        log_frame.grid(row=0, column=1, sticky="nsew")

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=16, pady=(16, 10))

        ctk.CTkLabel(
            log_header, text="진행 로그",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")

        self._log_text = scrolledtext.ScrolledText(
            log_frame, state="disabled", wrap="word",
            font=("Consolas", 9), bg=COLOR_LOG_BG, fg="#EEEAF5",
            insertbackground="white", relief="flat", bd=0,
            padx=12, pady=10,
        )
        self._log_text.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._log_text.tag_config("ERROR", foreground="#FFB4AB")
        self._log_text.tag_config("OK",    foreground="#91F0C4")
        self._log_text.tag_config("INFO",  foreground="#EEEAF5")

        # 하단: 버튼
        btn_frame = ctk.CTkFrame(
            self.root,
            fg_color=COLOR_PANEL,
            corner_radius=0,
            height=76,
        )
        btn_frame.grid(row=2, column=0, sticky="ew")
        btn_frame.pack_propagate(False)

        btn_inner = ctk.CTkFrame(btn_frame, fg_color="transparent")
        btn_inner.pack(fill="both", expand=True, padx=20, pady=16)

        status_box = ctk.CTkFrame(
            btn_inner,
            fg_color=COLOR_PRIMARY_SOFT,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_PRIMARY_LINE,
        )
        status_box.pack(side="left", fill="y")

        self._status_dot = ctk.CTkLabel(
            status_box,
            text="●",
            width=18,
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            text_color=COLOR_WARN,
        )
        self._status_dot.pack(side="left", padx=(16, 6), pady=8)

        self._status_label = ctk.CTkLabel(
            status_box,
            text="STATUS : 연동 확인 중",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLOR_TEXT,
        )
        self._status_label.pack(side="left", padx=(0, 16), pady=8)

        self._low_port_check = ctk.CTkCheckBox(
            btn_inner,
            text="낮은연동포트번호 사용",
            variable=self._low_port_var,
            width=160,
            checkbox_width=18,
            checkbox_height=18,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_DARK,
            border_color=COLOR_PRIMARY_LINE,
        )
        self._low_port_check.pack(side="left", padx=(12, 0), pady=10)

        self._remove_btn = ctk.CTkButton(
            btn_inner, text="연동 삭제",
            width=128, height=42,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color="#FFFFFF", hover_color="#FDECEC",
            text_color=COLOR_ERR, border_width=1, border_color="#F3B9B5",
            command=self._on_remove,
        )
        self._remove_btn.pack(side="right", padx=(6, 0))

        self._start_btn = ctk.CTkButton(
            btn_inner, text="연동 시작",
            width=144, height=42,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_DARK,
            text_color="#FFFFFF",
            command=self._on_start,
        )
        self._start_btn.pack(side="right")

    # ── 단계 목록 리셋 ────────────────────────
    def _reset_steps(self, steps: List[str]) -> None:
        for i, (icon_lbl, text_lbl) in enumerate(self._step_labels):
            label = steps[i] if i < len(steps) else ""
            icon_lbl.configure(text=STATUS_WAIT if label else "", text_color=COLOR_WAIT)
            text_lbl.configure(text=label, text_color=COLOR_WAIT)
            self._step_rows[i].configure(fg_color="transparent")

    # ── 단계 상태 업데이트 (스레드 안전) ──────
    def _set_step(self, idx: int, status: str) -> None:
        icon_lbl, text_lbl = self._step_labels[idx]
        color_map = {
            STATUS_WAIT: COLOR_WAIT,
            STATUS_RUN:  COLOR_RUN,
            STATUS_OK:   COLOR_OK,
            STATUS_ERR:  COLOR_ERR,
        }
        color = color_map.get(status, COLOR_WAIT)
        row_color = COLOR_PRIMARY_SOFT if status == STATUS_RUN else "transparent"
        icon_lbl.configure(text=status, text_color=color)
        text_lbl.configure(text_color=color)
        self._step_rows[idx].configure(fg_color=row_color)

    def _step_update(self, idx: int, status: str) -> None:
        self.root.after(0, lambda: self._set_step(idx, status))

    # ── 버튼 활성/비활성 (스레드 안전) ────────
    def _set_buttons(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.root.after(0, lambda: self._start_btn.configure(state=state))
        self.root.after(0, lambda: self._remove_btn.configure(state=state))
        self.root.after(0, lambda: self._low_port_check.configure(state=state))

    def _finish_action(self) -> None:
        self._start_btn.configure(state="normal")
        self._remove_btn.configure(state="normal")
        self._low_port_check.configure(state="normal")
        self.root.after(300, self._refresh_status)

    # ── 현재 연동 상태 표시 ───────────────────
    def _set_status(self, state: str, text: str) -> None:
        color_map = {
            "checking": COLOR_WARN,
            "linked": COLOR_OK,
            "missing": COLOR_ERR,
        }
        self._status_dot.configure(text_color=color_map.get(state, COLOR_WAIT))
        self._status_label.configure(text=text)

    def _refresh_status(self) -> None:
        self._status_refresh_id += 1
        refresh_id = self._status_refresh_id
        startup_logger.log_startup_event(
            "status_check_scheduled",
            "refresh_id={}".format(refresh_id),
        )
        self._set_status("checking", "STATUS : 연동 확인 중")
        threading.Thread(
            target=self._refresh_status_worker,
            args=(refresh_id,),
            daemon=True,
        ).start()

    def _refresh_status_worker(self, refresh_id: int) -> None:
        started_at = time.perf_counter()
        startup_logger.log_startup_event(
            "status_check_start",
            "refresh_id={}".format(refresh_id),
        )
        is_linked, status_text = self._check_linkage_status()
        elapsed = time.perf_counter() - started_at
        startup_logger.log_startup_event(
            "status_check_finish",
            "refresh_id={} | linked={} | elapsed={:0.3f}s | text={}".format(
                refresh_id,
                is_linked,
                elapsed,
                status_text,
            ),
        )
        state = "linked" if is_linked else "missing"
        self.root.after(
            0,
            lambda: self._apply_status_result(refresh_id, state, status_text),
        )

    def _apply_status_result(self, refresh_id: int, state: str, status_text: str) -> None:
        if refresh_id != self._status_refresh_id:
            return
        self._set_status(state, status_text)

    def _check_linkage_status(self) -> Tuple[bool, str]:
        try:
            installs = moaline_detector.detect_moaline()
            if not installs:
                return False, "STATUS : 연동 미설치"

            install = installs[0]
            linkage = config_writer.read_linkage_settings(install.ini_path)
            pos_port = linkage.get("POS1", "")
            moa_port = linkage.get("MOA1", "")
            print_port = linkage.get("PRINT1", "")

            if not _is_com_port(pos_port) or not _is_com_port(moa_port):
                return False, "STATUS : 연동 미설치"

            if install.kind == "plus":
                if linkage.get("PRNYN", "") != "1" and not _is_com_port(print_port):
                    return False, "STATUS : 연동 미설치"
            else:
                if not _is_com_port(print_port):
                    return False, "STATUS : 연동 미설치"
                if not linkage.get("Settings", "").startswith(BAUD_RATE):
                    return False, "STATUS : 연동 미설치"

            location = c0c.get_install_location()
            if not location:
                return False, "STATUS : 연동 미설치"

            setupc_path = c0c.get_setupc_path(location)
            pairs = c0c.get_port_pairs(setupc_path)
            required_ports = {pos_port.upper(), moa_port.upper()}
            for pair in pairs:
                pair_ports = {pair["port_a"].upper(), pair["port_b"].upper()}
                if required_ports.issubset(pair_ports):
                    return True, "STATUS : 연동 완료 : ({})".format(pos_port)

            return False, "STATUS : 연동 미설치"
        except Exception:
            return False, "STATUS : 연동 미설치"

    # ── 로그 (스레드 안전) ────────────────────
    def _append_log(self, message: str, level: str = "INFO") -> None:
        def _do():
            self._log_text.config(state="normal")
            self._log_text.insert("end", message + "\n", level)
            self._log_text.see("end")
            self._log_text.config(state="disabled")
        self.root.after(0, _do)

    def log(self, msg: str)    -> None: self._append_log(msg, "INFO")
    def log_ok(self, msg: str) -> None: self._append_log(msg, "OK")
    def log_err(self, msg: str)-> None: self._append_log(msg, "ERROR")

    # ════════════════════════════════════════
    # 연동 시작 흐름
    # ════════════════════════════════════════
    def _on_start(self) -> None:
        self._use_low_ports = bool(self._low_port_var.get())
        self._set_buttons(False)
        self.root.after(0, lambda: self._reset_steps(INSTALL_STEPS))
        threading.Thread(target=self._run_install_steps, daemon=True).start()

    def _run_install_steps(self) -> None:
        try:
            setupc_path = self._install_step_com0com()
            port_a, port_b = self._install_step_ports(setupc_path)
            install = self._detect_moaline(idx=2)
            self._install_step_config(install, port_a, port_b)
            self._install_step_dirs(install)
            self._restart_step(install, idx=5)
            self.root.after(0, lambda: CompletionDialog(self.root, port_a))
        except Exception as e:
            self.log_err("오류: {}".format(e))
            self.root.after(0, lambda: show_error_and_exit(self.root))
        finally:
            self.root.after(0, self._finish_action)

    def _install_step_com0com(self) -> str:
        self._step_update(0, STATUS_RUN)
        self.log("▶ com0com 설치 확인 중...")
        location = c0c.get_install_location()
        if location:
            self.log_ok("  이미 설치됨: {}".format(location))
            self._step_update(0, STATUS_OK)
            return c0c.get_setupc_path(location)

        self.log("  미설치 — 다운로드 시작...")

        def progress(pct: int) -> None:
            self.log("  다운로드: {}%".format(pct))

        c0c.download_zip(progress_cb=progress)
        self.log("  압축 해제 중...")
        c0c.extract_zip()
        self.log("  드라이버 설치 중 (잠시 기다려 주세요)...")

        if not c0c.install_driver():
            raise RuntimeError("com0com 드라이버 설치에 실패했습니다.")

        location = c0c.get_install_location()
        if not location:
            raise RuntimeError("설치 후 com0com 경로를 찾을 수 없습니다.")

        self.log_ok("  설치 완료: {}".format(location))
        self._step_update(0, STATUS_OK)
        return c0c.get_setupc_path(location)

    def _install_step_ports(self, setupc_path: str) -> Tuple[str, str]:
        self._step_update(1, STATUS_RUN)
        self.log("▶ 가상 COM 포트 생성 중...")
        if self._use_low_ports:
            self.log("  낮은 연동 포트번호 우선 사용")
            port_a, port_b = c0c.find_low_available_port_pair(setupc_path)
        else:
            port_a, port_b = c0c.find_available_port_pair(setupc_path)
        self.log("  선택된 포트: {} / {}".format(port_a, port_b))
        c0c.create_virtual_ports(setupc_path, port_a, port_b)
        self.log_ok("  포트 생성 완료 ({} ↔ {})".format(port_a, port_b))
        self._step_update(1, STATUS_OK)
        return port_a, port_b

    def _install_step_config(self, install, port_a: str, port_b: str) -> None:
        self._step_update(3, STATUS_RUN)
        self.log("▶ 설정 파일 수정: {}".format(install.ini_path))
        if install.kind == "plus":
            config_writer.write_moaline_plus_ini(install.ini_path, port_a, port_b)
        else:
            config_writer.write_moaline_store_ini(install.ini_path, port_a, port_b)
        self.log_ok("  설정 파일 수정 완료 (백업 생성됨)")
        self._step_update(3, STATUS_OK)

    def _install_step_dirs(self, install) -> None:
        self._step_update(4, STATUS_RUN)
        if install.kind == "plus":
            self.log("▶ COM 로그 폴더 생성 중...")
            config_writer.create_moaline_plus_dirs(install.install_dir)
            self.log_ok("  폴더 생성 완료")
        else:
            self.log("  (모아라인 상점 — 폴더 생성 불필요)")
        self._step_update(4, STATUS_OK)

    # ════════════════════════════════════════
    # 연동 제거 흐름
    # ════════════════════════════════════════
    def _on_remove(self) -> None:
        self._set_buttons(False)
        self.root.after(0, lambda: self._reset_steps(REMOVE_STEPS))
        threading.Thread(target=self._run_remove_steps, daemon=True).start()

    def _run_remove_steps(self) -> None:
        try:
            install = self._detect_moaline(idx=0)
            linkage = config_writer.read_linkage_settings(install.ini_path)
            port_a = linkage.get("POS1", DEFAULT_PORT_A)
            port_b = linkage.get("MOA1", DEFAULT_PORT_B)
            self._remove_step_config(install)
            self._remove_step_ports(port_a, port_b)
            self._restart_step(install, idx=3)
            self.root.after(0, lambda: RemoveCompletionDialog(self.root))
        except Exception as e:
            self.log_err("오류: {}".format(e))
            self.root.after(0, lambda: show_error_and_exit(self.root))
        finally:
            self.root.after(0, self._finish_action)

    def _remove_step_config(self, install) -> None:
        self._step_update(1, STATUS_RUN)
        self.log("▶ 설정 파일 복원 중: {}".format(install.ini_path))
        msg = config_writer.restore_ini(install.ini_path)
        self.log_ok("  {}".format(msg))
        self._step_update(1, STATUS_OK)

    def _remove_step_ports(self, port_a: str, port_b: str) -> None:
        self._step_update(2, STATUS_RUN)
        self.log("▶ 가상 COM 포트 제거 중...")
        location = c0c.get_install_location()
        if not location:
            self.log("  com0com 미설치 — 포트 제거 생략")
            self._step_update(2, STATUS_OK)
            return
        setupc_path = c0c.get_setupc_path(location)
        removed = c0c.remove_ports_by_name(setupc_path, port_a, port_b)
        if removed:
            self.log_ok("  가상 포트 제거 완료")
        else:
            self.log("  제거할 가상 포트를 찾지 못했습니다 (이미 제거됨)")
        self._step_update(2, STATUS_OK)

    # ════════════════════════════════════════
    # 공통 단계
    # ════════════════════════════════════════
    def _detect_moaline(self, idx: int):
        self._step_update(idx, STATUS_RUN)
        self.log("▶ 모아라인 프로그램 감지 중...")
        installs = moaline_detector.detect_moaline()
        if not installs:
            self._step_update(idx, STATUS_ERR)
            raise RuntimeError("모아라인 플러스 또는 상점이 설치되어 있지 않습니다.")
        chosen = installs[0]
        kind_kor = "플러스" if chosen.kind == "plus" else "상점"
        self.log_ok("  감지됨: 모아라인 {} ({})".format(kind_kor, chosen.install_dir))
        self._step_update(idx, STATUS_OK)
        return chosen

    def _restart_step(self, install, idx: int) -> None:
        self._step_update(idx, STATUS_RUN)
        self.log("▶ 모아라인 재시작 중...")
        exe_name = os.path.basename(install.exe_path)
        process_handler.restart_program(exe_name, install.exe_path)
        self.log_ok("  재시작 완료")
        self._step_update(idx, STATUS_OK)


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────
def main() -> None:
    startup_logger.log_startup_event("admin_check_start")
    admin.ensure_admin()
    startup_logger.log_startup_event("admin_check_finish")
    root = ctk.CTk()
    App(root)
    startup_logger.log_startup_event("mainloop_start")
    root.mainloop()
    startup_logger.log_startup_event("mainloop_finish")


if __name__ == "__main__":
    main()
