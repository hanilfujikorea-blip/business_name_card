from __future__ import annotations

import hashlib
import json
import secrets
from html import escape
from pathlib import Path
from typing import Any, Mapping


def draft_batch_digest(payload: Mapping[str, Any]) -> str:
    canonical: list[dict[str, Any]] = []
    for item in payload.get("drafts") or []:
        if item.get("status") != "ready":
            continue
        canonical.append(
            {
                "draft_id": str(item.get("draft_id") or ""),
                "source_hash": str(item.get("source_hash") or ""),
                "vendor_to": str(item.get("vendor_to") or ""),
                "vendor_cc": str(item.get("vendor_cc") or ""),
                "subject": str(item.get("subject") or ""),
                "html_body": str(item.get("html_body") or ""),
                "attachment_paths": [str(path) for path in item.get("attachment_paths") or []],
            }
        )
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_send_request(
    expected_token: str, supplied_token: str, expected_digest: str, supplied_digest: str
) -> bool:
    return bool(
        expected_token
        and supplied_token
        and expected_digest
        and supplied_digest
        and secrets.compare_digest(expected_token, supplied_token)
        and secrets.compare_digest(expected_digest, supplied_digest)
    )


def render_send_confirmation(payload: Mapping[str, Any], csrf_token: str) -> str:
    ready = [item for item in payload.get("drafts") or [] if item.get("status") == "ready"]
    digest = draft_batch_digest(payload)
    rows: list[str] = []
    for item in ready:
        attachments = ", ".join(Path(str(path)).name for path in item.get("attachment_paths") or []) or "없음"
        rows.append(
            "<tr>"
            f"<th>수신자</th><td>{escape(str(item.get('vendor_to') or '-'))}</td>"
            f"<th>참조</th><td>{escape(str(item.get('vendor_cc') or '-'))}</td>"
            "</tr>"
            "<tr>"
            f"<th>제목</th><td colspan='3'>{escape(str(item.get('subject') or '-'))}</td>"
            "</tr>"
            "<tr>"
            f"<th>신청 인원</th><td>{escape(str(item.get('request_count') or 0))}명</td>"
            f"<th>첨부파일</th><td>{escape(attachments)}</td>"
            "</tr>"
        )
    body = "".join(rows) if rows else "<tr><td>발송 가능한 초안이 없습니다.</td></tr>"
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>명함 발주 최종 확인</title>
  <style>
    body {{ font-family:'Malgun Gothic',sans-serif; background:#f3f6fb; color:#1f2b45; margin:0; }}
    main {{ max-width:960px; margin:32px auto; background:#fff; padding:28px; border-radius:20px; }}
    table {{ width:100%; border-collapse:collapse; margin:20px 0; }}
    th,td {{ border:1px solid #dbe3ef; padding:12px; text-align:left; }}
    th {{ background:#eef4fc; white-space:nowrap; }}
    .warning {{ background:#fff3cd; border:1px solid #ffe08a; padding:14px; border-radius:12px; }}
    .actions {{ display:flex; gap:12px; }}
    button,a {{ border:0; border-radius:999px; padding:12px 18px; font-weight:700; text-decoration:none; }}
    button {{ background:#b4372e; color:#fff; cursor:pointer; }}
    a {{ background:#e9eef6; color:#22324d; }}
  </style>
</head>
<body><main>
  <h1>발송 내용을 최종 확인하세요</h1>
  <p class="warning">아래 내용으로 실제 업체 메일이 발송됩니다. 수신자와 첨부파일을 반드시 확인하세요.</p>
  <table>{body}</table>
  <div class="actions">
    <form method="post" action="/action/send">
      <input type="hidden" name="csrf_token" value="{escape(csrf_token, quote=True)}">
      <input type="hidden" name="draft_digest" value="{escape(digest, quote=True)}">
      <button type="submit">확인했고 발송합니다</button>
    </form>
    <a href="/">취소하고 돌아가기</a>
  </div>
</main></body></html>"""
