from __future__ import annotations

import re
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from business_card_storage import OperationLock


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _split_addresses(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r"[;,\n]", raw) if item.strip()]


def validate_draft_for_send(
    draft: Mapping[str, Any], sent_hashes: Mapping[str, Any], file_hasher: Callable[[Path], str]
) -> list[str]:
    errors: list[str] = []
    source = Path(str(draft.get("source_file") or ""))
    source_hash = str(draft.get("source_hash") or "")
    if not source.is_file():
        errors.append("원본 신청서 파일이 없습니다.")
    elif not source_hash or file_hasher(source) != source_hash:
        errors.append("원본 신청서가 초안 생성 후 변경되었습니다.")

    recipients = _split_addresses(str(draft.get("vendor_to") or ""))
    if not recipients or any(not EMAIL_PATTERN.match(address) for address in recipients):
        errors.append("업체 수신자 이메일 주소가 올바르지 않습니다.")

    cc_recipients = _split_addresses(str(draft.get("vendor_cc") or ""))
    if any(not EMAIL_PATTERN.match(address) for address in cc_recipients):
        errors.append("업체 참조 이메일 주소가 올바르지 않습니다.")

    attachments = [Path(str(path)) for path in draft.get("attachment_paths") or []]
    missing = [path.name or str(path) for path in attachments if not path.is_file()]
    if missing:
        errors.append(f"첨부파일을 찾을 수 없습니다: {', '.join(missing)}")

    if source_hash and source_hash in sent_hashes:
        errors.append("이미 발송된 신청서입니다.")
    return errors


def send_ready_drafts_safely(
    payload: Mapping[str, Any],
    state: dict[str, Any] | None,
    archive_module: Any,
    save_state_callback: Callable[[dict[str, Any]], None],
    save_result_callback: Callable[[dict[str, Any]], None],
    lock_path: Path,
    file_hasher: Callable[[Path], str],
    state_loader: Callable[[], dict[str, Any]] | None = None,
    operation_locked: bool = False,
) -> dict[str, Any]:
    ready = [item for item in payload.get("drafts") or [] if item.get("status") == "ready"]
    if not ready:
        raise RuntimeError("발송 가능한 초안이 없습니다. 먼저 build 결과를 확인하세요.")

    state_payload = state
    sent_hashes: dict[str, Any] = {}
    results: list[dict[str, Any]] = []
    batch_started_at = datetime.now().isoformat(timespec="seconds")

    def current_result() -> dict[str, Any]:
        return {
            "sent_at": batch_started_at,
            "total_count": len(results),
            "success_count": sum(1 for item in results if item.get("ok")),
            "fail_count": sum(1 for item in results if not item.get("ok")),
            "results": list(results),
        }

    def persist_progress() -> None:
        if state_payload is None:
            raise RuntimeError("발송 상태를 불러올 수 없습니다.")
        state_payload["sent_hashes"] = sent_hashes
        save_state_callback(state_payload)
        save_result_callback(current_result())

    lock_context = nullcontext() if operation_locked else OperationLock(lock_path)
    with lock_context:
        if state_loader is not None:
            state_payload = state_loader()
        if state_payload is None:
            raise RuntimeError("발송 상태를 불러올 수 없습니다.")
        sent_hashes = state_payload.get("sent_hashes") or {}
        session = archive_module.open_mailer_session(run_id="business_card_order")
        try:
            client = session["client"]
            config = session["config"]
            sender_address, sender_personal, _ = client.guess_sender_account(
                preferred_address=config.from_address,
                preferred_personal=config.from_personal,
            )
            for item in ready:
                now = datetime.now().isoformat(timespec="seconds")
                source_hash = str(item.get("source_hash") or "")
                errors = validate_draft_for_send(item, sent_hashes, file_hasher)
                if errors:
                    skipped = source_hash in sent_hashes
                    results.append(
                        {
                            "draft_id": item.get("draft_id"),
                            "subject": item.get("subject"),
                            "source_file": item.get("source_file"),
                            "ok": bool(skipped),
                            "skipped": bool(skipped),
                            "reason": "already_sent" if skipped else "preflight_failed",
                            "message": " ".join(errors),
                            "sent_at": now,
                        }
                    )
                    persist_progress()
                    continue

                try:
                    response = client.send_message(
                        to_txt=str(item.get("vendor_to") or ""),
                        cc_txt=str(item.get("vendor_cc") or ""),
                        subject=str(item.get("subject") or ""),
                        html_content=str(item.get("html_body") or ""),
                        from_address=sender_address,
                        from_personal=sender_personal,
                        select_sign=str(config.select_sign or "0"),
                        priority=str(config.priority or "3"),
                        attachments=[Path(str(path)) for path in item.get("attachment_paths") or []],
                    )
                    result_row = {
                        "draft_id": item.get("draft_id"),
                        "subject": item.get("subject"),
                        "source_file": item.get("source_file"),
                        "ok": bool(response.get("ok")),
                        "status": response.get("status"),
                        "code": response.get("code"),
                        "message": response.get("message") or response.get("error") or "",
                        "sent_at": now,
                    }
                except Exception as exc:
                    result_row = {
                        "draft_id": item.get("draft_id"),
                        "subject": item.get("subject"),
                        "source_file": item.get("source_file"),
                        "ok": False,
                        "message": str(exc),
                        "sent_at": now,
                    }
                if result_row["ok"] and source_hash:
                    sent_hashes[source_hash] = {
                        "sent_at": now,
                        "source_file": item.get("source_file"),
                        "draft_id": item.get("draft_id"),
                        "subject": item.get("subject"),
                    }
                results.append(result_row)
                persist_progress()
        finally:
            archive_module.close_mailer_session(session, run_id="business_card_order")

        result_payload = current_result()
        history = state_payload.get("send_history") or []
        history.insert(
            0,
            {
                "sent_at": result_payload["sent_at"],
                "success_count": result_payload["success_count"],
                "fail_count": result_payload["fail_count"],
                "total_count": result_payload["total_count"],
                "note": "승인 후 업체 발주 메일 전송",
            },
        )
        state_payload["send_history"] = history[:50]
        persist_progress()
        return result_payload
