from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from business_card_storage import atomic_save_json, load_json


VALID_SEND_MODES = {"manual", "automatic"}
SEND_MODE_LABELS = {
    "manual": "직접 승인 중",
    "automatic": "자동 발송 중",
}


def load_automation_settings(path: Path) -> dict[str, str]:
    try:
        payload = load_json(path, {})
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return {"send_mode": "manual"}
    if not isinstance(payload, dict):
        return {"send_mode": "manual"}
    mode = payload.get("send_mode")
    if not isinstance(mode, str):
        return {"send_mode": "manual"}
    return {"send_mode": mode if mode in VALID_SEND_MODES else "manual"}


def save_send_mode(path: Path, mode: str) -> dict[str, str]:
    if mode not in VALID_SEND_MODES:
        raise ValueError("지원하지 않는 발송 모드입니다.")
    payload = {"send_mode": mode}
    atomic_save_json(path, payload)
    return payload


def send_mode_label(mode: str) -> str:
    return SEND_MODE_LABELS[mode]


def select_new_ready_payload(sync_result: Mapping[str, Any]) -> dict[str, Any]:
    def normalized_path(value: Any) -> str | None:
        if not isinstance(value, (str, os.PathLike)):
            return None
        return os.path.normcase(str(Path(value).resolve()))

    fetch_payload = sync_result.get("fetch")
    fetch_results = (
        fetch_payload.get("results") or []
        if isinstance(fetch_payload, Mapping)
        else []
    )
    imported_files = {
        normalized
        for result in fetch_results
        if isinstance(result, Mapping) and result.get("status") == "imported"
        for saved_file in (result.get("saved_files") or [])
        if (normalized := normalized_path(saved_file)) is not None
    }

    original_payload = sync_result.get("drafts")
    selected_payload = (
        dict(original_payload) if isinstance(original_payload, Mapping) else {}
    )
    original_drafts = selected_payload.get("drafts") or []
    selected_drafts = [
        draft
        for draft in original_drafts
        if isinstance(draft, Mapping)
        and draft.get("status") == "ready"
        and normalized_path(draft.get("source_file")) in imported_files
    ]
    selected_payload.update(
        drafts=selected_drafts,
        draft_count=len(selected_drafts),
        ready_count=len(selected_drafts),
        pending_count=0,
    )
    return selected_payload


def run_automation_cycle(
    sync_cycle: Callable[[], dict],
    send_payload: Callable[[dict], dict],
    settings_path: Path,
) -> dict[str, Any]:
    sync_result = sync_cycle()
    send_mode = load_automation_settings(settings_path)["send_mode"]
    selected_count = 0
    send_result = None
    if send_mode == "automatic":
        selected_payload = select_new_ready_payload(sync_result)
        selected_count = selected_payload["draft_count"]
        if selected_count:
            send_result = send_payload(selected_payload)
    return {
        "sync": sync_result,
        "send_mode": send_mode,
        "selected_count": selected_count,
        "send": send_result,
    }
