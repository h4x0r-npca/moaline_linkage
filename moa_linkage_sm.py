import ctypes
import os
import sys
import tkinter as tk
from tkinter import scrolledtext
from typing import Dict, List

import customtkinter as ctk
from PIL import Image, ImageTk

from build_info import APP_VERSION, RELEASE_DATE
from serial_monitor_core import (
    COM_ROOT,
    PortSettings,
    ReceiptLogWriter,
    ensure_com_dirs,
    list_physical_ports,
    load_config,
    parse_hex_patterns,
    save_config,
)


AGENT_MUTEX = "Local\\MoalineLinkageSerialMonitor"
ERROR_ALREADY_EXISTS = 183

COLOR_PRIMARY = "#570DCA"
COLOR_PRIMARY_DARK = "#4700A8"
COLOR_PRIMARY_SOFT = "#F3ECFF"
COLOR_PRIMARY_LINE = "#D7C4FF"
COLOR_TEXT = "#191124"
COLOR_MUTED = "#70677D"
COLOR_OK = "#139E66"
COLOR_ERR = "#D92D20"
COLOR_WARN = "#B7791F"
COLOR_BG = "#F7F4FB"
COLOR_PANEL = "#FFFFFF"
COLOR_LOG_BG = "#17131F"
FONT_FAMILY = "맑은 고딕"


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def acquire_single_instance() -> bool:
    ctypes.windll.kernel32.SetLastError(0)
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, AGENT_MUTEX)
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
        return False
    return True


class ToastWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, message: str) -> None:
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.95)
        self.configure(bg="#202124")
        label = tk.Label(
            self,
            text=message,
            bg="#202124",
            fg="#FFFFFF",
            font=(FONT_FAMILY, 10, "bold"),
            padx=18,
            pady=12,
        )
        label.pack()
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry("+{}+{}".format(sw - w - 24, sh - h - 60))
        self.after(2200, self._fade)

    def _fade(self) -> None:
        alpha = float(self.attributes("-alpha"))
        if alpha <= 0.05:
            self.destroy()
            return
        self.attributes("-alpha", alpha - 0.08)
        self.after(45, self._fade)


class SerialMonitorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("모아라인 모니터링연동 Ver {} (Release : {})".format(
            APP_VERSION,
            RELEASE_DATE,
        ))
        self.root.geometry("980x700")
        self.root.minsize(920, 650)
        self.root.configure(fg_color=COLOR_BG)
        self.root.protocol("WM_DELETE_WINDOW", self._hide_window)

        ensure_com_dirs()
        self.available_ports = list_physical_ports()
        self.config = load_config(self.available_ports)
        self.config.direct_monitor_enabled = False
        self._ensure_config_ports()

        self.port_vars: Dict[str, ctk.BooleanVar] = {}
        self.port_tabs: Dict[str, scrolledtext.ScrolledText] = {}
        self.settings_vars: Dict[str, tk.StringVar] = {}
        self.current_settings_port = tk.StringVar(value="")
        self.writer = ReceiptLogWriter()
        self.tray_icon = None
        self.tray_available = False
        self._icon_photo = None

        self._set_window_icon()
        self._build_ui()
        self._load_settings_form()
        self._start_tray()
        self._set_idle_status()
        self.root.after(700, self._startup_notice)

    def _ensure_config_ports(self) -> None:
        for port in self.available_ports:
            self.config.port_settings.setdefault(port, PortSettings())
        save_config(self.config)

    def _set_window_icon(self) -> None:
        icon_path = resource_path("moaline.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)
            return
        logo_path = resource_path("로고.webp")
        if os.path.exists(logo_path):
            image = Image.open(logo_path).resize((64, 64))
            self._icon_photo = ImageTk.PhotoImage(image)
            self.root.iconphoto(True, self._icon_photo)

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self.root, fg_color=COLOR_PRIMARY, corner_radius=0, height=86)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True, padx=22, pady=14)
        ctk.CTkLabel(
            title_box,
            text="모니터링연동 설정",
            font=ctk.CTkFont(family=FONT_FAMILY, size=23, weight="bold"),
            text_color="#FFFFFF",
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box,
            text="상점 출력은 그대로 두고, 드라이버 후킹 방식으로 지나가는 데이터만 복사하도록 준비합니다.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color="#EEE4FF",
        ).pack(anchor="w", pady=(4, 0))

        self.status_label = ctk.CTkLabel(
            header,
            text="● 감시 준비 중",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color="#FFE2A8",
        )
        self.status_label.pack(side="right", padx=22)

        content = ctk.CTkFrame(self.root, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=18, pady=18)
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        settings_panel = ctk.CTkFrame(
            content,
            fg_color=COLOR_PANEL,
            corner_radius=10,
            border_width=1,
            border_color=COLOR_PRIMARY_LINE,
            width=330,
        )
        settings_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        settings_panel.grid_propagate(False)

        ctk.CTkLabel(
            settings_panel,
            text="테스트 포트 선택",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=16, pady=(16, 8))

        self.port_list_frame = ctk.CTkScrollableFrame(settings_panel, fg_color="#FBFAFD", height=140)
        self.port_list_frame.pack(fill="x", padx=14, pady=(0, 10))
        self._render_port_checks()

        ctk.CTkLabel(
            settings_panel,
            text="포트별 고급설정",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=16, pady=(8, 8))

        self.port_option = ctk.CTkOptionMenu(
            settings_panel,
            variable=self.current_settings_port,
            values=self.available_ports or ["포트 없음"],
            command=lambda _: self._load_settings_form(),
            fg_color=COLOR_PRIMARY,
            button_color=COLOR_PRIMARY_DARK,
            button_hover_color=COLOR_PRIMARY_DARK,
        )
        self.port_option.pack(fill="x", padx=14, pady=(0, 8))
        if self.available_ports:
            self.current_settings_port.set(self.available_ports[0])

        fields = [
            ("baudrate", "Baudrate"),
            ("parity", "Parity"),
            ("stopbits", "Stopbits"),
            ("bytesize", "Bytesize"),
            ("flow_control", "Flow"),
            ("encoding", "Encoding"),
            ("idle_timeout_ms", "Idle(ms)"),
            ("min_bytes", "Min bytes"),
        ]
        for key, label in fields:
            row = ctk.CTkFrame(settings_panel, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(
                row,
                text=label,
                width=92,
                anchor="w",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=COLOR_MUTED,
            ).pack(side="left")
            var = tk.StringVar()
            self.settings_vars[key] = var
            ctk.CTkEntry(row, textvariable=var, height=28).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            settings_panel,
            text="컷 명령 HEX",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_MUTED,
        ).pack(anchor="w", padx=16, pady=(8, 3))
        self.cut_text = tk.Text(
            settings_panel,
            height=3,
            font=("Consolas", 9),
            bg="#FBFAFD",
            fg=COLOR_TEXT,
            relief="solid",
            bd=1,
        )
        self.cut_text.pack(fill="x", padx=14, pady=(0, 10))

        actions = ctk.CTkFrame(settings_panel, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(2, 14))
        ctk.CTkButton(
            actions,
            text="설정 저장",
            command=self.save_settings,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_DARK,
            width=96,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="포트 새로고침",
            command=self.refresh_ports,
            fg_color="#FFFFFF",
            hover_color=COLOR_PRIMARY_SOFT,
            text_color=COLOR_PRIMARY,
            border_width=1,
            border_color=COLOR_PRIMARY_LINE,
            width=104,
        ).pack(side="left", padx=6)
        self.monitor_toggle_btn = ctk.CTkButton(
            actions,
            text="드라이버 후킹 준비 중",
            command=self.show_driver_pending,
            fg_color="#FFFFFF",
            hover_color="#FFF4E5",
            text_color=COLOR_WARN,
            border_width=1,
            border_color="#F3C77F",
            width=104,
        )
        self.monitor_toggle_btn.pack(side="left")

        log_panel = ctk.CTkFrame(
            content,
            fg_color=COLOR_PANEL,
            corner_radius=10,
            border_width=1,
            border_color=COLOR_PRIMARY_LINE,
        )
        log_panel.grid(row=0, column=1, sticky="nsew")
        log_panel.grid_rowconfigure(1, weight=1)
        log_panel.grid_columnconfigure(0, weight=1)

        log_header = ctk.CTkFrame(log_panel, fg_color="transparent")
        log_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        ctk.CTkLabel(
            log_header,
            text="실시간 로그 미리보기",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")
        ctk.CTkButton(
            log_header,
            text="로그 폴더 열기",
            command=self.open_log_folder,
            fg_color="#FFFFFF",
            hover_color=COLOR_PRIMARY_SOFT,
            text_color=COLOR_PRIMARY,
            border_width=1,
            border_color=COLOR_PRIMARY_LINE,
            width=112,
        ).pack(side="right")

        self.tabview = ctk.CTkTabview(log_panel, fg_color="#FBFAFD", segmented_button_selected_color=COLOR_PRIMARY)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self._sync_tabs()

    def _render_port_checks(self) -> None:
        for child in self.port_list_frame.winfo_children():
            child.destroy()
        self.port_vars.clear()
        if not self.available_ports:
            ctk.CTkLabel(
                self.port_list_frame,
                text="감지된 물리 COM 포트가 없습니다.",
                text_color=COLOR_MUTED,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            ).pack(anchor="w", padx=8, pady=8)
            return
        selected = {p.upper() for p in self.config.selected_ports}
        for port in self.available_ports:
            var = ctk.BooleanVar(value=port.upper() in selected)
            self.port_vars[port] = var
            ctk.CTkCheckBox(
                self.port_list_frame,
                text=port,
                variable=var,
                command=self._port_selection_changed,
                checkbox_width=18,
                checkbox_height=18,
                fg_color=COLOR_PRIMARY,
                hover_color=COLOR_PRIMARY_DARK,
                border_color=COLOR_PRIMARY_LINE,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            ).pack(anchor="w", padx=8, pady=4)

    def _selected_ports(self) -> List[str]:
        return [port for port, var in self.port_vars.items() if bool(var.get())]

    def _port_selection_changed(self) -> None:
        self.config.selected_ports = self._selected_ports()
        for port in self.config.selected_ports:
            self.config.port_settings.setdefault(port, PortSettings())
        save_config(self.config)
        self._sync_tabs()
        self._set_idle_status()

    def _sync_tabs(self) -> None:
        selected = self._selected_ports() if self.port_vars else list(self.config.selected_ports)
        for port in list(self.port_tabs):
            if port not in selected:
                try:
                    self.tabview.delete(port)
                except Exception:
                    pass
                self.port_tabs.pop(port, None)

        for port in selected:
            if port in self.port_tabs:
                continue
            tab = self.tabview.add(port)
            text = scrolledtext.ScrolledText(
                tab,
                state="disabled",
                wrap="word",
                font=("Consolas", 9),
                bg=COLOR_LOG_BG,
                fg="#EEEAF5",
                insertbackground="white",
                relief="flat",
                bd=0,
                padx=10,
                pady=8,
            )
            text.pack(fill="both", expand=True, padx=6, pady=6)
            self.port_tabs[port] = text

    def _load_settings_form(self) -> None:
        port = self.current_settings_port.get()
        settings = self.config.port_settings.get(port, PortSettings())
        for key, var in self.settings_vars.items():
            var.set(str(getattr(settings, key)))
        if hasattr(self, "cut_text"):
            self.cut_text.delete("1.0", "end")
            self.cut_text.insert("1.0", settings.cut_patterns_hex)

    def save_settings(self) -> None:
        port = self.current_settings_port.get()
        if not port or port == "포트 없음":
            return
        try:
            settings = PortSettings(
                baudrate=int(self.settings_vars["baudrate"].get()),
                parity=self.settings_vars["parity"].get().upper()[:1] or "N",
                stopbits=float(self.settings_vars["stopbits"].get()),
                bytesize=int(self.settings_vars["bytesize"].get()),
                flow_control=self.settings_vars["flow_control"].get().lower() or "none",
                encoding=self.settings_vars["encoding"].get() or "cp949",
                cut_patterns_hex=self.cut_text.get("1.0", "end").strip(),
                idle_timeout_ms=int(self.settings_vars["idle_timeout_ms"].get()),
                min_bytes=int(self.settings_vars["min_bytes"].get()),
            )
            parse_hex_patterns(settings.cut_patterns_hex)
            self.config.port_settings[port] = settings
            self.config.selected_ports = self._selected_ports()
            save_config(self.config)
            self._append_port_log(port, "[설정 저장 완료]\n")
            self._set_idle_status()
        except Exception as exc:
            self._show_toast("설정 저장 실패: {}".format(exc))

    def refresh_ports(self) -> None:
        self.available_ports = list_physical_ports()
        for port in self.available_ports:
            self.config.port_settings.setdefault(port, PortSettings())
        self._render_port_checks()
        self.port_option.configure(values=self.available_ports or ["포트 없음"])
        self.current_settings_port.set(self.available_ports[0] if self.available_ports else "포트 없음")
        self._load_settings_form()
        self._sync_tabs()
        save_config(self.config)
        self._set_idle_status()

    def show_driver_pending(self) -> None:
        self._show_toast("운영 매장 안전을 위해 직접 COM 감시는 비활성화되어 있습니다.")
        for port in self._selected_ports():
            self._append_port_log(
                port,
                "[대기] 직접 COM 감시는 포트를 점유하므로 비활성화되었습니다.\n"
                "[대기] 무료/오픈소스 드라이버 후킹 PoC가 완료되면 이 포트 설정을 사용합니다.\n",
            )

    def _set_idle_status(self) -> None:
        selected = self._selected_ports() if self.port_vars else list(self.config.selected_ports)
        text = "● 안전 대기 중 (COM 포트 점유 안 함)"
        if selected:
            text = "● 안전 대기 중: {}개 포트 설정됨".format(len(selected))
        self.status_label.configure(text=text, text_color="#FFE2A8")
        if hasattr(self, "monitor_toggle_btn"):
            self.monitor_toggle_btn.configure(
                text="드라이버 후킹 준비 중",
                text_color=COLOR_WARN,
                border_color="#F3C77F",
            )

    def _write_receipt(self, port: str, data: bytes) -> None:
        try:
            paths = self.writer.write(port, data)
            self._append_port_log(port, "\n[LOG 저장] {}\n".format(os.path.basename(paths[0])))
        except Exception as exc:
            self._append_port_log(port, "\n[LOG 저장 실패] {}\n".format(exc), error=True)

    def _append_port_log(self, port: str, text: str, error: bool = False) -> None:
        def _do() -> None:
            widget = self.port_tabs.get(port)
            if not widget:
                return
            widget.config(state="normal")
            widget.insert("end", text)
            if error:
                widget.insert("end", "")
            lines = int(widget.index("end-1c").split(".")[0])
            if lines > 1500:
                widget.delete("1.0", "{}.0".format(lines - 1200))
            widget.see("end")
            widget.config(state="disabled")
        self.root.after(0, _do)

    def open_log_folder(self) -> None:
        os.startfile(COM_ROOT)

    def _start_tray(self) -> None:
        try:
            import pystray
        except Exception:
            self.tray_available = False
            return

        icon_path = resource_path("moaline.ico")
        image = Image.open(icon_path) if os.path.exists(icon_path) else Image.new("RGB", (64, 64), COLOR_PRIMARY)
        menu = pystray.Menu(
            pystray.MenuItem("열기", lambda icon=None, item=None: self.root.after(0, self._show_window)),
            pystray.MenuItem("로그 폴더 열기", lambda icon=None, item=None: self.root.after(0, self.open_log_folder)),
            pystray.MenuItem("종료", lambda icon=None, item=None: self.root.after(0, self._exit_app)),
        )
        self.tray_icon = pystray.Icon("moa_linkage_sm", image, "모아라인 모니터링연동", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self.tray_available = True

    def _startup_notice(self) -> None:
        self._show_toast("모아라인 연동 프로그램 구동에 성공하였습니다.")
        if self.tray_icon:
            try:
                self.tray_icon.notify("모아라인 연동 프로그램 구동에 성공하였습니다.")
            except Exception:
                pass
        if self.tray_available:
            self._hide_window()

    def _show_toast(self, message: str) -> None:
        try:
            ToastWindow(self.root, message)
        except Exception:
            pass

    def _hide_window(self) -> None:
        self.root.withdraw()

    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _exit_app(self) -> None:
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()


def main() -> None:
    if not acquire_single_instance():
        return
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    SerialMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
