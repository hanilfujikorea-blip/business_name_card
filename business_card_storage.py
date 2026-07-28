from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any


class OperationLockedError(RuntimeError):
    """Raised when another process owns the business-card operation lock."""


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def recover_json_file(path: Path, backup_root: Path, required_keys: set[str]) -> Path:
    raw = path.read_text(encoding="utf-8-sig")
    payload, _ = json.JSONDecoder().raw_decode(raw.lstrip())
    if not isinstance(payload, dict):
        raise ValueError(f"복구 대상 JSON의 최상위 값이 객체가 아닙니다: {path}")
    missing = sorted(required_keys - set(payload))
    if missing:
        raise ValueError(f"복구 대상 JSON에 필수 키가 없습니다: {', '.join(missing)}")
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / path.name
    if backup_path.exists():
        raise FileExistsError(f"백업 파일이 이미 존재합니다: {backup_path}")
    backup_path.write_bytes(path.read_bytes())
    atomic_save_json(path, payload)
    return backup_path


class OperationLock:
    def __init__(self, path: Path, stale_after_sec: int = 3600) -> None:
        self.path = path
        self.stale_after_sec = max(int(stale_after_sec), 1)
        self.token = secrets.token_hex(16)
        self.acquired = False

    def _is_stale(self) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            created_at = float(payload.get("created_at") or 0)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            try:
                created_at = self.path.stat().st_mtime
            except FileNotFoundError:
                return False
        return time.time() - created_at > self.stale_after_sec

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"pid": os.getpid(), "created_at": time.time(), "token": self.token},
            ensure_ascii=False,
        ).encode("utf-8")
        for attempt in range(2):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                if attempt == 0 and self._is_stale():
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                raise OperationLockedError(
                    "다른 동기화 또는 발송 작업이 진행 중입니다. 완료 후 다시 시도하세요."
                ) from exc
            try:
                os.write(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            self.acquired = True
            return
        raise OperationLockedError("작업 잠금을 획득할 수 없습니다.")

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("token") == self.token:
                self.path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        finally:
            self.acquired = False

    def __enter__(self) -> "OperationLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()
