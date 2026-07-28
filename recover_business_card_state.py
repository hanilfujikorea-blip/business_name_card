from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from business_card_storage import atomic_save_json


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"
FETCH_RESULT_PATH = OUTPUT_DIR / "business_card_mail_fetch_result.json"
STATE_PATH = OUTPUT_DIR / "processed_state.json"
BACKUP_ROOT = OUTPUT_DIR / "backups"

FETCH_KEYS = {"fetched_at", "mail_scan_count", "imported_count", "skipped_count", "results"}
STATE_KEYS = {"sent_hashes", "send_history", "fetched_message_uids", "import_history"}


def _decode_first_object(path: Path, required_keys: set[str]) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8-sig")
    payload, _ = json.JSONDecoder().raw_decode(raw.lstrip())
    if not isinstance(payload, dict):
        raise ValueError(f"복구 대상의 최상위 JSON 값이 객체가 아닙니다: {path}")
    missing = sorted(required_keys - set(payload))
    if missing:
        raise ValueError(f"{path.name}에 필수 키가 없습니다: {', '.join(missing)}")
    return payload


def recover_paths(fetch_path: Path, state_path: Path, backup_root: Path) -> dict[str, Any]:
    fetch_payload = _decode_first_object(fetch_path, FETCH_KEYS)
    state_payload = _decode_first_object(state_path, STATE_KEYS)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_dir = backup_root / timestamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    (backup_dir / fetch_path.name).write_bytes(fetch_path.read_bytes())
    (backup_dir / state_path.name).write_bytes(state_path.read_bytes())

    atomic_save_json(fetch_path, fetch_payload)
    atomic_save_json(state_path, state_payload)
    return {"fetch": fetch_payload, "state": state_payload, "backup_dir": backup_dir}


def main() -> int:
    result = recover_paths(FETCH_RESULT_PATH, STATE_PATH, BACKUP_ROOT)
    state = result["state"]
    print(f"백업 위치: {result['backup_dir']}")
    print(f"보존된 발송 해시: {len(state.get('sent_hashes') or {})}건")
    print(f"보존된 발송 이력: {len(state.get('send_history') or [])}건")
    print("상태 파일 복구와 JSON 검증을 완료했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
