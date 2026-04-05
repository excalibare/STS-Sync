from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from sts_syn.config import AppConfig
from sts_syn.models import DeviceInfo
from sts_syn.service import EnvironmentStatus, SyncService
from sts_syn.utils.time_utils import format_dt


class QueueLogHandler(logging.Handler):
    def __init__(self, target_queue: queue.Queue[tuple[str, object]]) -> None:
        super().__init__()
        self.target_queue = target_queue
        self.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.target_queue.put(('log', self.format(record)))
        except Exception:
            self.handleError(record)


class MainWindow:
    def __init__(self, root: tk.Tk, config: AppConfig, logger: logging.Logger, dry_run: bool = False) -> None:
        self.root = root
        self.config = config
        self.logger = logger
        self.dry_run = dry_run
        self.service = SyncService(config=config, logger=logger, dry_run=dry_run)
        self.ui_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.busy = False
        self.current_status: EnvironmentStatus | None = None
        self.selected_serial_var = tk.StringVar(value=config.device_serial or '')
        self.config_path_var = tk.StringVar(value=str(config.config_path))
        self.adb_status_var = tk.StringVar(value='Checking...')
        self.device_status_var = tk.StringVar(value='Checking...')
        self.android_status_var = tk.StringVar(value='Checking...')
        self.pc_status_var = tk.StringVar(value='Checking...')
        self.online_devices: list[DeviceInfo] = []
        self.action_buttons: list[ttk.Button] = []
        self.detect_button: ttk.Button | None = None
        self.device_combo: ttk.Combobox | None = None
        self.log_text: tk.Text | None = None
        self.log_handler = QueueLogHandler(self.ui_queue)
        self.logger.addHandler(self.log_handler)

        self.root.title('STS Sync')
        self.root.geometry('980x700')
        self.root.minsize(900, 620)
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)

        self._build_ui()
        self.root.after(150, self.process_ui_queue)
        self.root.after(250, self.refresh_status)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        config_frame = ttk.LabelFrame(outer, text='Configuration', padding=10)
        config_frame.grid(row=0, column=0, sticky='ew')
        config_frame.columnconfigure(1, weight=1)
        ttk.Label(config_frame, text='Config file:').grid(row=0, column=0, sticky='w')
        ttk.Label(config_frame, textvariable=self.config_path_var).grid(row=0, column=1, sticky='w')
        ttk.Label(config_frame, text='Device serial:').grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.device_combo = ttk.Combobox(config_frame, textvariable=self.selected_serial_var, state='readonly')
        self.device_combo.grid(row=1, column=1, sticky='ew', pady=(8, 0))

        status_frame = ttk.LabelFrame(outer, text='Status', padding=10)
        status_frame.grid(row=1, column=0, sticky='nsew', pady=(12, 0))
        status_frame.columnconfigure(1, weight=1)
        for index, (label, variable) in enumerate(
            (
                ('ADB:', self.adb_status_var),
                ('Device:', self.device_status_var),
                ('Android paths:', self.android_status_var),
                ('PC paths:', self.pc_status_var),
            )
        ):
            ttk.Label(status_frame, text=label).grid(row=index, column=0, sticky='nw', padx=(0, 8), pady=3)
            ttk.Label(status_frame, textvariable=variable, justify=tk.LEFT).grid(row=index, column=1, sticky='w', pady=3)

        buttons_frame = ttk.Frame(outer)
        buttons_frame.grid(row=2, column=0, sticky='ew', pady=(12, 0))
        for idx in range(5):
            buttons_frame.columnconfigure(idx, weight=1)

        self.detect_button = ttk.Button(buttons_frame, text='检测设备', command=self.refresh_status)
        self.detect_button.grid(row=0, column=0, sticky='ew', padx=4, pady=4)
        self._make_action_button(buttons_frame, 'pull-progress', 'pull-progress', 0, 1)
        self._make_action_button(buttons_frame, 'push-progress', 'push-progress', 0, 2)
        self._make_action_button(buttons_frame, 'sync-safe', 'sync-safe', 0, 3)
        self._make_action_button(buttons_frame, 'pull-save', 'pull-save', 1, 0)
        self._make_action_button(buttons_frame, 'push-save', 'push-save', 1, 1, dangerous=True)

        open_logs = ttk.Button(buttons_frame, text='打开日志目录', command=self.open_log_dir)
        open_logs.grid(row=1, column=2, sticky='ew', padx=4, pady=4)
        self.action_buttons.append(open_logs)

        open_backups = ttk.Button(buttons_frame, text='打开备份目录', command=self.open_backup_dir)
        open_backups.grid(row=1, column=3, sticky='ew', padx=4, pady=4)
        self.action_buttons.append(open_backups)

        note = ttk.Label(
            buttons_frame,
            text='提示: sync-safe 只同步 preferences；push-save 仍会走危险保护与备份逻辑。',
            justify=tk.LEFT,
        )
        note.grid(row=2, column=0, columnspan=5, sticky='w', padx=4, pady=(8, 0))

        log_frame = ttk.LabelFrame(outer, text='Logs', padding=10)
        log_frame.grid(row=3, column=0, sticky='nsew', pady=(12, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, wrap='word', height=20, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _make_action_button(
        self,
        parent: ttk.Frame,
        text: str,
        command_name: str,
        row: int,
        column: int,
        dangerous: bool = False,
    ) -> None:
        button = ttk.Button(
            parent,
            text=text,
            command=lambda: self.start_command(command_name, dangerous=dangerous),
        )
        button.grid(row=row, column=column, sticky='ew', padx=4, pady=4)
        self.action_buttons.append(button)

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        if self.detect_button is not None:
            self.detect_button.configure(state=state)
        if self.device_combo is not None:
            self.device_combo.configure(state='disabled' if busy else 'readonly')
        for button in self.action_buttons:
            button.configure(state=state)

    def append_log(self, message: str) -> None:
        if self.log_text is None:
            return
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def process_ui_queue(self) -> None:
        while True:
            try:
                kind, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            if kind == 'log':
                self.append_log(str(payload))
            elif kind == 'status':
                self.apply_status(payload)  # type: ignore[arg-type]
            elif kind == 'status_done':
                self.set_busy(False)
                if payload:
                    self.append_log(str(payload))
            elif kind == 'command_done':
                self.set_busy(False)
                if payload:
                    self.append_log(str(payload))
                self.refresh_status()
            elif kind == 'error':
                self.set_busy(False)
                messagebox.showerror('STS Sync', str(payload))
        self.root.after(150, self.process_ui_queue)

    def get_selected_serial(self) -> str | None:
        value = self.selected_serial_var.get().strip()
        return value or None

    def ensure_serial_ready(self) -> bool:
        if self.current_status is None:
            return False
        if self.current_status.serial_required and not self.get_selected_serial():
            messagebox.showwarning('STS Sync', '检测到多台设备，请先从下拉框选择一个 serial。')
            return False
        return True

    def refresh_status(self) -> None:
        if self.busy:
            return
        self.set_busy(True)

        def worker() -> None:
            try:
                status = self.service.inspect_environment(device_serial=self.get_selected_serial())
                self.ui_queue.put(('status', status))
                self.ui_queue.put(('status_done', '状态检测完成'))
            except Exception as exc:
                self.ui_queue.put(('error', exc))

        threading.Thread(target=worker, daemon=True).start()

    def apply_status(self, status: EnvironmentStatus) -> None:
        self.current_status = status
        self.online_devices = [item for item in status.devices if item.state == 'device']
        if self.device_combo is not None:
            values = [item.serial for item in self.online_devices]
            self.device_combo['values'] = values
            if status.selected_serial:
                self.selected_serial_var.set(status.selected_serial)
            elif values:
                self.selected_serial_var.set('')

        self.adb_status_var.set('可用' if status.adb_available else f'不可用: {self.config.adb_path}')
        self.device_status_var.set(status.device_message)

        android_lines = [f'Root: {self.config.android_root} (exists={status.android_root_exists})']
        if status.android_root_detected:
            android_lines.append(f'Candidate root detected: {status.android_root_detected}')
        for component, dir_status in status.android_status.items():
            android_lines.append(
                f'{component}: exists={dir_status.exists}, files={dir_status.file_count or 0}, latest={format_dt(dir_status.latest_mtime)}'
            )
        self.android_status_var.set('\n'.join(android_lines))

        pc_lines = [f'Root: {self.config.pc_root} (exists={status.pc_root_exists})']
        for component, dir_status in status.pc_status.items():
            pc_lines.append(
                f'{component}: exists={dir_status.exists}, files={dir_status.file_count or 0}, latest={format_dt(dir_status.latest_mtime)}'
            )
        self.pc_status_var.set('\n'.join(pc_lines))

        if status.serial_required:
            messagebox.showinfo('STS Sync', '检测到多台设备，请从 Device serial 下拉框选择要操作的设备。')

    def start_command(self, command_name: str, dangerous: bool = False) -> None:
        if self.busy:
            return
        if not self.ensure_serial_ready():
            return
        if dangerous:
            first = messagebox.askyesno(
                '危险操作确认',
                'push-save 会覆盖 Android 端当前对局存档，且可能导致进度损坏。\n\n是否继续？',
                icon=messagebox.WARNING,
            )
            if not first:
                return
            second = messagebox.askyesno(
                '二次确认',
                '请再次确认：两端游戏都已退出，且你明确要覆盖 saves。\n\n继续执行 push-save？',
                icon=messagebox.WARNING,
            )
            if not second:
                return

        self.set_busy(True)
        serial = self.get_selected_serial()
        self.append_log(f'开始执行: {command_name} serial={serial or "<auto>"}')

        def worker() -> None:
            try:
                force = command_name == 'push-save'
                self.service.run_command(command_name, device_serial=serial, force=force)
                self.ui_queue.put(('command_done', f'执行完成: {command_name}'))
            except Exception as exc:
                self.ui_queue.put(('error', exc))

        threading.Thread(target=worker, daemon=True).start()

    def open_log_dir(self) -> None:
        self.config.log_root.mkdir(parents=True, exist_ok=True)
        os.startfile(self.config.log_root)  # type: ignore[attr-defined]

    def open_backup_dir(self) -> None:
        self.config.backup_root.mkdir(parents=True, exist_ok=True)
        os.startfile(self.config.backup_root)  # type: ignore[attr-defined]

    def on_close(self) -> None:
        try:
            self.logger.removeHandler(self.log_handler)
        except Exception:
            pass
        self.log_handler.close()
        self.root.destroy()


def launch_gui(config: AppConfig, logger: logging.Logger, dry_run: bool = False) -> int:
    root = tk.Tk()
    MainWindow(root=root, config=config, logger=logger, dry_run=dry_run)
    root.mainloop()
    return 0
