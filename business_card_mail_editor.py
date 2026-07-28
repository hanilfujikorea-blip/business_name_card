from __future__ import annotations

import copy
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import business_card_mailer as mailer
from business_card_storage import atomic_save_json, load_json


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EDITABLE_FIELDS = (
    "vendor_to",
    "vendor_cc",
    "subject",
    "greeting_text",
    "request_text",
    "closing_text",
)
BULK_FIELDS = (
    "vendor_to",
    "vendor_cc",
    "greeting_text",
    "request_text",
    "closing_text",
)


def split_addresses(raw: str) -> list[str]:
    return [value.strip() for value in re.split(r"[;,\n]", raw) if value.strip()]


def split_text_lines(raw: str) -> list[str]:
    return str(raw or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")


def split_template_copy(template: Mapping[str, Any]) -> tuple[str, str, str]:
    intro = [str(line) for line in template.get("intro_lines") or []]
    closing = [str(line) for line in template.get("closing_lines") or []]
    greeting = intro[0] if intro else ""
    request = "\n".join(intro[1:])
    return greeting, request, "\n".join(closing)


def validate_editor_values(values: Mapping[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    recipients = split_addresses(str(values.get("vendor_to") or ""))
    if not recipients:
        errors["vendor_to"] = "수신자를 한 명 이상 입력하세요."
    for field in ("vendor_to", "vendor_cc"):
        addresses = split_addresses(str(values.get(field) or ""))
        if any(not EMAIL_PATTERN.fullmatch(address) for address in addresses):
            errors[field] = "올바른 이메일 주소를 입력하세요."
    if not str(values.get("subject") or "").strip():
        errors["subject"] = "제목을 입력하세요."
    return errors


def validate_recipient_values(values: Mapping[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    recipients = split_addresses(str(values.get("vendor_to") or ""))
    if not recipients:
        errors["vendor_to"] = "받는 사람을 입력하세요."
    elif any(not EMAIL_PATTERN.fullmatch(address) for address in recipients):
        errors["vendor_to"] = "올바른 이메일 주소를 입력하세요."

    copies = split_addresses(str(values.get("vendor_cc") or ""))
    if any(not EMAIL_PATTERN.fullmatch(address) for address in copies):
        errors["vendor_cc"] = "올바른 이메일 주소를 입력하세요."
    return errors


def update_default_recipients(
    template: Mapping[str, Any], vendor_to: str, vendor_cc: str
) -> dict[str, Any]:
    updated = copy.deepcopy(dict(template))
    updated["vendor_to"] = str(vendor_to or "").strip()
    updated["vendor_cc"] = str(vendor_cc or "").strip()
    return updated


def save_default_recipients(
    template_path: Path,
    template: Mapping[str, Any],
    values: Mapping[str, Any],
) -> dict[str, str]:
    errors = validate_recipient_values(values)
    if errors:
        return errors
    updated = update_default_recipients(
        template,
        str(values.get("vendor_to") or ""),
        str(values.get("vendor_cc") or ""),
    )
    atomic_save_json(template_path, updated)
    return {}

def load_overrides(path: Path) -> dict[str, Any]:
    try:
        payload = load_json(path, {"drafts": {}})
    except (OSError, ValueError, TypeError):
        return {"drafts": {}}
    if not isinstance(payload, dict):
        return {"drafts": {}}
    if not isinstance(payload.get("drafts"), dict):
        payload["drafts"] = {}
    return payload


def values_for_draft(draft: Mapping[str, Any], template: Mapping[str, Any]) -> dict[str, str]:
    greeting, request, closing = split_template_copy(template)
    return {
        "vendor_to": str(draft.get("vendor_to") or ""),
        "vendor_cc": str(draft.get("vendor_cc") or ""),
        "subject": str(draft.get("subject") or ""),
        "greeting_text": greeting,
        "request_text": request,
        "closing_text": closing,
    }


def _normalized_values(values: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in fields:
        value = str(values.get(field) or "")
        if field.endswith("_text"):
            value = value.replace("\r\n", "\n").replace("\r", "\n")
        else:
            value = value.strip()
        result[field] = value
    return result


def _rebuild_body(
    draft: dict[str, Any], template: Mapping[str, Any], values: Mapping[str, str]
) -> None:
    temporary_template = copy.deepcopy(dict(template))
    temporary_template["intro_lines"] = (
        split_text_lines(values.get("greeting_text") or "")
        + split_text_lines(values.get("request_text") or "")
    )
    temporary_template["closing_lines"] = split_text_lines(values.get("closing_text") or "")
    context = mailer.build_context_from_requests(
        draft.get("requests") or [],
        str(draft.get("request_date") or ""),
    )
    draft["html_body"] = mailer.build_mail_html(
        context,
        draft.get("requests") or [],
        temporary_template,
    )


def effective_payload(
    payload: Mapping[str, Any],
    template: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(dict(payload))
    override_items = overrides.get("drafts") if isinstance(overrides, Mapping) else {}
    if not isinstance(override_items, Mapping):
        override_items = {}
    for draft in result.get("drafts") or []:
        if draft.get("status") != "ready":
            continue
        saved = override_items.get(str(draft.get("draft_id") or ""))
        if not isinstance(saved, Mapping):
            continue
        if str(saved.get("source_hash") or "") != str(draft.get("source_hash") or ""):
            continue
        values = values_for_draft(draft, template)
        for field in EDITABLE_FIELDS:
            if field in saved:
                values[field] = str(saved.get(field) or "")
        for field in ("vendor_to", "vendor_cc", "subject"):
            draft[field] = values[field]
        _rebuild_body(draft, template, values)
        draft["editor_values"] = values
        draft["has_override"] = True
    return result


def _find_ready_draft(
    payload: Mapping[str, Any], draft_id: str, source_hash: str
) -> Mapping[str, Any] | None:
    for draft in payload.get("drafts") or []:
        if (
            draft.get("status") == "ready"
            and str(draft.get("draft_id") or "") == draft_id
            and str(draft.get("source_hash") or "") == source_hash
        ):
            return draft
    return None


def save_editor_action(
    scope: str,
    payload: Mapping[str, Any],
    template: Mapping[str, Any],
    override_path: Path,
    template_path: Path,
    draft_id: str,
    source_hash: str,
    values: Mapping[str, Any],
) -> dict[str, str]:
    errors = validate_editor_values(values)
    if errors:
        return errors
    selected = _find_ready_draft(payload, draft_id, source_hash)
    if selected is None:
        return {"form": "초안이 변경되었습니다. 화면을 새로 열어 다시 확인하세요."}

    if scope == "defaults":
        updated_template = copy.deepcopy(dict(template))
        normalized = _normalized_values(values, EDITABLE_FIELDS)
        updated_template["vendor_to"] = normalized["vendor_to"]
        updated_template["vendor_cc"] = normalized["vendor_cc"]
        updated_template["intro_lines"] = (
            split_text_lines(normalized["greeting_text"])
            + split_text_lines(normalized["request_text"])
        )
        updated_template["closing_lines"] = split_text_lines(normalized["closing_text"])
        atomic_save_json(template_path, updated_template)
        return {}

    current = load_overrides(override_path)
    saved_drafts = current["drafts"]
    if scope == "one":
        saved_drafts[draft_id] = {
            "source_hash": source_hash,
            **_normalized_values(values, EDITABLE_FIELDS),
        }
    elif scope == "all":
        common = _normalized_values(values, BULK_FIELDS)
        for draft in payload.get("drafts") or []:
            if draft.get("status") != "ready":
                continue
            current_item = saved_drafts.get(str(draft.get("draft_id") or ""))
            preserved_subject = None
            if isinstance(current_item, Mapping) and "subject" in current_item:
                preserved_subject = str(current_item.get("subject") or "")
            item = {
                "source_hash": str(draft.get("source_hash") or ""),
                **common,
            }
            if preserved_subject is not None:
                item["subject"] = preserved_subject
            saved_drafts[str(draft.get("draft_id") or "")] = item
    else:
        return {"form": "지원하지 않는 저장 방식입니다."}

    current["updated_at"] = datetime.now().isoformat(timespec="seconds")
    atomic_save_json(override_path, current)
    return {}

def render_mail_editor(
    payload: Mapping[str, Any],
    template: Mapping[str, Any],
    overrides: Mapping[str, Any],
    csrf_token: str,
    send_mode: str = "manual",
    selected_id: str = "",
    notice: str = "",
    errors: Mapping[str, str] | None = None,
    posted_values: Mapping[str, Any] | None = None,
) -> str:
    from business_card_mail_editor_page import render_mail_editor_page

    return render_mail_editor_page(
        payload=payload,
        template=template,
        overrides=overrides,
        csrf_token=csrf_token,
        send_mode=send_mode,
        selected_id=selected_id,
        notice=notice,
        errors=errors,
        posted_values=posted_values,
    )
