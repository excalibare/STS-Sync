from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sts_syn.models import CommandResult, DeviceInfo, DirStatus


class AdbError(RuntimeError):
    """Raised when an adb operation fails."""


class ADBClient:
    def __init__(
        self,
        adb_path: str,
        logger: logging.Logger,
        device_serial: str | None = None,
        dry_run: bool = False,
    ) -> None:
        self.adb_path = adb_path
        self.logger = logger
        self.device_serial = device_serial
        self.dry_run = dry_run

    def _build_command(self, *args: str, include_serial: bool = True) -> list[str]:
        command = [self.adb_path]
        if include_serial and self.device_serial:
            command.extend(['-s', self.device_serial])
        command.extend(args)
        return command

    def _run(
        self, *args: str, include_serial: bool = True, check: bool = False
    ) -> CommandResult:
        command = self._build_command(*args, include_serial=include_serial)
        self.logger.debug('Running command: %s', command)
        if self.dry_run and any(arg in {'pull', 'push'} for arg in args):
            self.logger.info('[dry-run] Skip adb transfer: %s', ' '.join(command))
            return CommandResult(command, 0, '', '')

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise AdbError(f'adb executable not found: {self.adb_path}') from exc
        except OSError as exc:
            raise AdbError(f'failed to execute adb: {exc}') from exc

        result = CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )
        if check and not result.ok:
            raise AdbError(
                f"adb command failed ({result.returncode}): {' '.join(command)}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return result

    def check_adb_available(self) -> bool:
        if self.adb_path != 'adb' and not Path(self.adb_path).exists():
            return False
        if self.adb_path == 'adb' and shutil.which('adb') is None:
            return False
        return self._run('version', include_serial=False).ok

    def list_devices(self) -> list[DeviceInfo]:
        result = self._run('devices', include_serial=False, check=True)
        devices: list[DeviceInfo] = []
        for line in result.stdout.splitlines()[1:]:
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            if len(parts) >= 2:
                devices.append(DeviceInfo(serial=parts[0], state=parts[1]))
        return devices

    def resolve_device(self, preferred_serial: str | None = None) -> str:
        if preferred_serial:
            self.device_serial = preferred_serial
            return preferred_serial
        devices = [item for item in self.list_devices() if item.state == 'device']
        if not devices:
            raise AdbError('no online adb device detected')
        if len(devices) > 1:
            serials = ', '.join(item.serial for item in devices)
            raise AdbError(
                'multiple adb devices detected, please set device_serial in config '
                f'or pass --device-serial. devices: {serials}'
            )
        self.device_serial = devices[0].serial
        return self.device_serial

    def shell(self, command: str, check: bool = False) -> CommandResult:
        return self._run('shell', command, check=check)

    def pull(self, remote_path: str, local_path: Path, check: bool = True) -> CommandResult:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        return self._run('pull', remote_path, str(local_path), check=check)

    def push(self, local_path: Path, remote_path: str, check: bool = True) -> CommandResult:
        return self._run('push', str(local_path), remote_path, check=check)

    def push_directory_contents(self, local_dir: Path, remote_dir: str, check: bool = True) -> None:
        if not local_dir.exists() or not local_dir.is_dir():
            raise AdbError(f'local directory does not exist: {local_dir}')
        self.ensure_remote_dir(remote_dir)
        for child in local_dir.iterdir():
            self.push(child, remote_dir, check=check)

    def path_exists(self, remote_path: str) -> bool:
        quoted = shlex.quote(remote_path)
        result = self.shell(f'if [ -e {quoted} ]; then echo 1; else echo 0; fi', check=True)
        return result.stdout.strip().endswith('1')

    def directory_exists(self, remote_path: str) -> bool:
        quoted = shlex.quote(remote_path)
        result = self.shell(f'if [ -d {quoted} ]; then echo 1; else echo 0; fi', check=True)
        return result.stdout.strip().endswith('1')

    def ensure_remote_dir(self, remote_path: str) -> None:
        if self.dry_run:
            self.logger.info('[dry-run] Would create remote directory: %s', remote_path)
            return
        self.shell(f'mkdir -p {shlex.quote(remote_path)}', check=True)

    def delete_remote_dir(self, remote_path: str) -> None:
        if self.dry_run:
            self.logger.info('[dry-run] Would delete remote directory: %s', remote_path)
            return
        self.shell(f'rm -rf {shlex.quote(remote_path)}', check=True)

    def move_remote_dir(self, source: str, target: str) -> None:
        if self.dry_run:
            self.logger.info('[dry-run] Would rename remote directory: %s -> %s', source, target)
            return
        self.shell(f'mv {shlex.quote(source)} {shlex.quote(target)}', check=True)

    def detect_first_existing_root(self, candidates: Iterable[str]) -> str | None:
        for candidate in candidates:
            if self.directory_exists(candidate):
                return candidate
        return None

    def remote_file_count(self, remote_path: str) -> int | None:
        if not self.directory_exists(remote_path):
            return None
        quoted = shlex.quote(remote_path)
        result = self.shell(
            f"find {quoted} -type f 2>/dev/null | wc -l | tr -d ' '", check=True
        )
        try:
            return int(result.stdout.strip() or '0')
        except ValueError:
            return None

    def remote_mtime(self, remote_path: str) -> datetime | None:
        if not self.path_exists(remote_path):
            return None
        quoted = shlex.quote(remote_path)
        for command in (f'stat -c %Y {quoted}', f'toybox stat -c %Y {quoted}'):
            result = self.shell(command)
            if result.ok and result.stdout.strip():
                try:
                    return datetime.fromtimestamp(int(result.stdout.strip().splitlines()[-1]))
                except ValueError:
                    continue
        return None

    def get_dir_status(self, remote_path: str) -> DirStatus:
        exists = self.directory_exists(remote_path)
        return DirStatus(
            path=remote_path,
            exists=exists,
            file_count=self.remote_file_count(remote_path) if exists else None,
            latest_mtime=self.remote_mtime(remote_path) if exists else None,
        )
