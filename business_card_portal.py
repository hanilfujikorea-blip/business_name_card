# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping

import json
import os
import secrets
import subprocess
import sys
import threading
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import business_card_mailer as mailer
from business_card_automation import (
    load_automation_settings,
    save_send_mode,
    send_mode_label,
)
from business_card_mail_editor import (
    EDITABLE_FIELDS,
    effective_payload,
    load_overrides,
    render_mail_editor,
    save_default_recipients,
    save_editor_action,
)
from business_card_portal_security import (
    draft_batch_digest,
    render_send_confirmation,
    validate_send_request,
)

ROOT = Path(__file__).resolve().parent
MAILER = ROOT / "business_card_mailer.py"
OUTPUT = ROOT / "output"
DRAFTS_PATH = OUTPUT / "business_card_drafts.json"
PREVIEW_PATH = OUTPUT / "business_card_preview.html"
DASHBOARD_PATH = OUTPUT / "business_card_dashboard.html"
FETCH_RESULT_PATH = OUTPUT / "business_card_mail_fetch_result.json"
SEND_RESULT_PATH = OUTPUT / "business_card_send_result.json"
OVERRIDES_PATH = OUTPUT / "business_card_send_overrides.json"
AUTOMATION_SETTINGS_PATH = ROOT / "inbox" / "automation_settings.json"
PORT = 8765
INTERVAL = max(int(os.getenv("BUSINESS_CARD_MONITOR_INTERVAL_SEC") or "60"), 10)
CSRF_TOKEN = secrets.token_urlsafe(32)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_mailer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-u", str(MAILER), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def summarize_error(raw: str) -> str:
    text = (raw or "").strip()
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    lowered = compact.lower()
    if "archive_base_url is empty" in lowered or "invalid archive_base_url" in lowered:
        return "메일 서버 주소 설정이 올바르지 않습니다. .env의 ARCHIVE_BASE_URL을 확인하세요."
    if "archive_username is empty" in lowered:
        return "메일 계정 아이디가 비어 있습니다. .env의 ARCHIVE_USERNAME을 확인하세요."
    if "archive_password is empty" in lowered:
        return "메일 계정 비밀번호가 비어 있습니다. .env의 ARCHIVE_PASSWORD를 확인하세요."
    if "login required" in lowered or "http 401" in lowered or "http 403" in lowered:
        return "메일 서버 로그인에 실패했습니다. 아이디, 비밀번호, 접근 권한을 확인하세요."
    if "winerror 10061" in lowered or "connectionrefusederror" in lowered or "network error" in lowered:
        return "메일 서버에 연결할 수 없습니다. 회사망/VPN 연결 또는 ARCHIVE_BASE_URL 접속 상태를 확인하세요."
    if "timed out" in lowered or "timeout" in lowered:
        return "메일 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도하세요."
    if compact:
        return compact[:220]
    return "처리 중 오류가 발생했습니다."


def sync_once() -> tuple[bool, str]:
    try:
        cycle_result = mailer.run_locked_automation_cycle(
            settings_path=AUTOMATION_SETTINGS_PATH,
        )
        sync_result = cycle_result["sync"]
        fetch = sync_result["fetch"]
        drafts = sync_result["drafts"]
        message = (
            f"새로고침 완료: 메일 {fetch.get('mail_scan_count', 0)}건 확인, "
            f"새로 가져옴 {fetch.get('imported_count', 0)}건, "
            f"발송 가능 {drafts.get('ready_count', 0)}건"
        )
        send_result = cycle_result["send"]
        if send_result is not None:
            message += (
                f", 자동 발송 성공 {send_result.get('success_count', 0)}건 / "
                f"실패 {send_result.get('fail_count', 0)}건"
            )
        return True, message
    except Exception as exc:
        return False, summarize_error(str(exc))


def send_once(payload: dict) -> tuple[bool, str]:
    try:
        result = mailer.send_ready_drafts(approve_send=True, payload=payload)
    except Exception as exc:
        return False, summarize_error(str(exc))
    return True, f"발송 완료: 성공 {result.get('success_count', 0)} / 실패 {result.get('fail_count', 0)}"


def portal_html(
    status_message: str = "",
    errors: Mapping[str, str] | None = None,
    posted_values: Mapping[str, str] | None = None,
) -> str:
    drafts = read_json(DRAFTS_PATH)
    fetch = read_json(FETCH_RESULT_PATH)
    send = read_json(SEND_RESULT_PATH)
    draft_items = drafts.get("drafts") or []
    last_draft = draft_items[0] if draft_items else {}
    source_file = Path(str(last_draft.get("source_file") or "-")).name
    subject = str(last_draft.get("subject") or "-")
    send_summary = (
        f"성공 {send.get('success_count', 0)} / 실패 {send.get('fail_count', 0)}"
        if send
        else "아직 발송 전"
    )
    notice = (
        f'<div class="notice" role="status">{escape(status_message)}</div>'
        if status_message
        else ""
    )

    send_mode = load_automation_settings(AUTOMATION_SETTINGS_PATH)["send_mode"]
    mode_label = send_mode_label(send_mode)
    manual_pressed = "true" if send_mode == "manual" else "false"
    automatic_pressed = "true" if send_mode == "automatic" else "false"
    mode_explanation = (
        "\uc0c8 \uba85\ud568 \uc2e0\uccad\uc11c\ub294 \uac80\uc99d \ud6c4 \uc989\uc2dc \ubc1c\uc1a1\ub429\ub2c8\ub2e4."
        if send_mode == "automatic"
        else "\ucd5c\uc885 \ud655\uc778 \ud6c4 \ubc1c\uc1a1\ub429\ub2c8\ub2e4."
    )
    template = mailer.load_template()
    values = posted_values if posted_values is not None else template
    vendor_to = escape(str(values.get("vendor_to") or ""), quote=True)
    vendor_cc = escape(str(values.get("vendor_cc") or ""), quote=True)
    field_errors = errors or {}
    vendor_to_error = (
        f'<p class="field-error" role="alert">{escape(str(field_errors["vendor_to"]))}</p>'
        if "vendor_to" in field_errors
        else ""
    )
    vendor_cc_error = (
        f'<p class="field-error" role="alert">{escape(str(field_errors["vendor_cc"]))}</p>'
        if "vendor_cc" in field_errors
        else ""
    )

    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>명함 발주 승인 포털</title>
  <style>
    * {{ box-sizing:border-box; }}
    body {{ font-family:Pretendard,'Noto Sans KR','Malgun Gothic',system-ui,sans-serif; margin:0; background:#F3EFE7; color:#282A25; }}
    button, input {{ font:inherit; }}
    button:focus-visible, input:focus-visible, a:focus-visible {{ outline:3px solid #B77945; outline-offset:2px; }}
    .wrap {{ max-width:1360px; margin:0 auto; padding:28px; }}
    .hero {{ background:#173F35; color:#FFFDF7; padding:28px; border:1px solid #173F35; border-radius:20px; box-shadow:0 10px 30px rgba(51,45,34,.06); }}
    .hero h1 {{ margin:0 0 8px; font-size:30px; font-weight:800; }}
    .hero p {{ margin:0; color:#DCEEE5; line-height:1.6; }}
    .actions {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:18px; }}
    .actions form {{ margin:0; }}
    button {{ border:1px solid transparent; border-radius:12px; padding:11px 16px; font-size:14px; font-weight:700; cursor:pointer; }}
    .primary {{ background:#FFFDF7; color:#173F35; border-color:#FFFDF7; }}
    .danger {{ background:#F6DEDB; color:#A33E36; border-color:#F6DEDB; }}
    .secondary {{ background:#245B4B; color:#FFFDF7; border-color:#DCEEE5; }}
    .notice {{ margin:16px 0; padding:14px 16px; border-radius:14px; background:#F7E2C3; border:1px solid #B77945; color:#97520F; line-height:1.6; }}
    .settings-panel, .card, .panel {{ background:#FFFDF7; border:1px solid #DDD6C8; border-radius:18px; box-shadow:0 10px 30px rgba(51,45,34,.06); }}
    .settings-panel {{ margin:20px 0; padding:22px; }}
    .settings-panel h2, .panel h2 {{ margin:0; font-size:20px; font-weight:800; color:#173F35; }}
    .settings-grid {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.3fr); gap:24px; margin-top:18px; }}
    .settings-block {{ min-width:0; }}
    .settings-label {{ margin:0 0 8px; color:#716F67; font-size:13px; font-weight:700; }}
    .mode-row {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:14px; }}
    .mode-badge {{ display:inline-flex; align-items:center; min-height:32px; padding:6px 11px; border-radius:999px; background:#DCEEE5; color:#176B50; font-weight:800; }}
    .mode-badge.automatic {{ background:#F7E2C3; color:#97520F; }}
    .mode-buttons {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
    .mode-button {{ width:100%; background:#FFFDF7; color:#173F35; border-color:#DDD6C8; }}
    .mode-button[aria-pressed="true"] {{ background:#173F35; color:#FFFDF7; border-color:#173F35; }}
    .mode-copy {{ margin:12px 0 0; color:#716F67; line-height:1.6; }}
    .recipient-form {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
    .form-field {{ min-width:0; }}
    .form-field label {{ display:block; margin-bottom:7px; color:#173F35; font-size:14px; font-weight:800; }}
    .form-field input {{ width:100%; min-height:44px; padding:10px 12px; color:#282A25; background:#FFFDF7; border:1px solid #DDD6C8; border-radius:10px; }}
    .field-error {{ margin:7px 0 0; color:#A33E36; font-size:13px; font-weight:700; }}
    .form-help {{ grid-column:1 / -1; margin:0; color:#716F67; font-size:13px; line-height:1.5; }}
    .save-settings {{ grid-column:1 / -1; justify-self:start; background:#B77945; color:#FFFDF7; border-color:#B77945; }}
    .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; margin:20px 0; }}
    .card {{ padding:18px 20px; }}
    .card strong {{ display:block; font-size:30px; color:#173F35; }}
    .panel {{ padding:20px; margin-bottom:16px; }}
    .meta {{ color:#716F67; line-height:1.7; }}
    iframe {{ width:100%; height:560px; border:1px solid #DDD6C8; border-radius:14px; background:#FFFDF7; }}
    @media (max-width:767px) {{
      .wrap {{ padding:14px; }}
      .hero {{ padding:22px; }}
      .settings-grid, .recipient-form, .mode-buttons {{ grid-template-columns:1fr; }}
      .form-help, .save-settings {{ grid-column:1; }}
      .actions, .actions form, .actions button {{ width:100%; }}
    }}
    @media (prefers-reduced-motion:reduce) {{ * {{ scroll-behavior:auto !important; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>명함 발주 승인 포털</h1>
      <p>메일로 들어온 신청서를 자동으로 모아서 검토하고, 승인 후 업체로 보낼 수 있습니다.</p>
      <div class="actions">
        <form method="post" action="/action/sync">
          <input type="hidden" name="csrf_token" value="{escape(CSRF_TOKEN, quote=True)}">
          <button class="primary" type="submit">지금 새로고침</button>
        </form>
        <form method="get" action="/confirm-send"><button class="danger" type="submit">발송 내용 확인</button></form>
        <form method="get" action="/dashboard"><button class="secondary" type="submit">대시보드 보기</button></form>
      </div>
    </section>
    {notice}
    <section class="settings-panel" aria-labelledby="settings-heading">
      <h2 id="settings-heading">운영 설정</h2>
      <div class="settings-grid">
        <div class="settings-block">
          <p class="settings-label">현재 발송 모드</p>
          <div class="mode-row">
            <span class="mode-badge{' automatic' if send_mode == 'automatic' else ''}">{escape(mode_label)}</span>
          </div>
          <form method="post" action="/action/set-send-mode" class="mode-buttons">
            <input type="hidden" name="csrf_token" value="{escape(CSRF_TOKEN, quote=True)}">
            <button class="mode-button" type="submit" name="send_mode" value="manual" aria-pressed="{manual_pressed}">직접 승인</button>
            <button class="mode-button" type="submit" name="send_mode" value="automatic" aria-pressed="{automatic_pressed}" onclick="return confirm('새 명함 신청서가 검증 후 외부 업체로 즉시 발송됩니다. 자동 발송으로 전환하시겠습니까?')">자동 발송</button>
          </form>
          <p class="mode-copy">{escape(mode_explanation)}</p>
        </div>
        <div class="settings-block">
          <p class="settings-label">업체 기본 수신 주소</p>
          <form method="post" action="/action/save-default-mail-settings" class="recipient-form" novalidate>
            <input type="hidden" name="csrf_token" value="{escape(CSRF_TOKEN, quote=True)}">
            <div class="form-field">
              <label for="vendor_to">받는 사람</label>
              <input id="vendor_to" name="vendor_to" type="text" value="{vendor_to}" autocomplete="off" required aria-describedby="vendor_to_help">
              {vendor_to_error}
            </div>
            <div class="form-field">
              <label for="vendor_cc">참조</label>
              <input id="vendor_cc" name="vendor_cc" type="text" value="{vendor_cc}" autocomplete="off" aria-describedby="vendor_to_help">
              {vendor_cc_error}
            </div>
            <p class="form-help" id="vendor_to_help">여러 주소는 쉼표 또는 세미콜론으로 구분해 입력하세요.</p>
            <button class="save-settings" type="submit">기본 발송 설정 저장</button>
          </form>
        </div>
      </div>
    </section>
    <section class="stats">
      <div class="card"><strong>{fetch.get('imported_count', 0)}</strong>이번 회차 가져온 메일</div>
      <div class="card"><strong>{drafts.get('request_file_count', 0)}</strong>신청 파일</div>
      <div class="card"><strong>{drafts.get('ready_count', 0)}</strong>발송 가능</div>
      <div class="card"><strong>{drafts.get('pending_count', 0)}</strong>확인 필요</div>
      <div class="card"><strong>{send.get('success_count', 0)}</strong>발송 성공 건수</div>
      <div class="card"><strong>{send.get('fail_count', 0)}</strong>발송 실패 건수</div>
    </section>
    <section class="panel">
      <h2>최근 처리 요약</h2>
      <div class="meta">최근 메일 제목: {escape(subject)}</div>
      <div class="meta">신청 파일: {escape(source_file)}</div>
      <div class="meta">최근 메일 수집 시각: {escape(str(fetch.get('fetched_at') or '-'))}</div>
      <div class="meta">최근 발송 결과: {escape(send_summary)}</div>
    </section>
    <section class="panel">
      <h2>미리보기</h2>
      <iframe src="/preview" title="명함 발주 메일 미리보기"></iframe>
    </section>
  </div>
</body>
</html>'''

class PortalHandler(BaseHTTPRequestHandler):
    status_message = ""

    def _write(self, body: bytes, content_type: str = "text/html; charset=utf-8", status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._write(portal_html(self.status_message).encode("utf-8"))
            return
        if path == "/preview" and PREVIEW_PATH.exists():
            self._write(PREVIEW_PATH.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/confirm-send":
            payload = mailer.load_drafts_payload()
            template = mailer.load_template()
            query = parse_qs(parsed.query)
            selected = str((query.get("draft") or [""])[0])
            saved = str((query.get("saved") or [""])[0])
            notices = {
                "one": "이번 발송에만 수정값을 저장했습니다.",
                "all": "수신·참조·문구를 준비된 모든 메일에 적용했습니다.",
                "defaults": "다음 자동발주부터 사용할 기본값을 저장했습니다.",
            }
            html = render_mail_editor(
                payload,
                template,
                load_overrides(OVERRIDES_PATH),
                CSRF_TOKEN,
                send_mode=load_automation_settings(AUTOMATION_SETTINGS_PATH)["send_mode"],
                selected_id=selected,
                notice=notices.get(saved, ""),
            )
            self._write(html.encode("utf-8"))
            return
        if path == "/dashboard":
            payload = mailer.load_drafts_payload()
            template = mailer.load_template()
            state = mailer.load_state()
            send_result = mailer.load_send_result()
            fetch_result = mailer.load_fetch_result()
            html = mailer.render_dashboard_html(
                payload,
                template,
                state,
                send_result,
                fetch_result,
                send_mode=load_automation_settings(AUTOMATION_SETTINGS_PATH)["send_mode"],
            )
            self._write(html.encode("utf-8"), "text/html; charset=utf-8")
            return
        self._write(b"not found", "text/plain; charset=utf-8", 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        form = parse_qs(body.decode("utf-8", errors="replace"))
        supplied_token = str((form.get("csrf_token") or [""])[0])
        if not supplied_token or not secrets.compare_digest(CSRF_TOKEN, supplied_token):
            self._write("요청 검증에 실패했습니다. 포털 화면에서 다시 시도하세요.".encode("utf-8"), "text/plain; charset=utf-8", 403)
            return
        if path == "/action/set-send-mode":
            mode = str((form.get("send_mode") or [""])[0])
            try:
                save_send_mode(AUTOMATION_SETTINGS_PATH, mode)
            except ValueError as exc:
                self._write(
                    str(exc).encode("utf-8"),
                    "text/plain; charset=utf-8",
                    400,
                )
                return
            PortalHandler.status_message = (
                "자동 발송 모드로 전환했습니다."
                if mode == "automatic"
                else "직접 승인 모드로 전환했습니다."
            )
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if path == "/action/save-default-mail-settings":
            values = {
                "vendor_to": str((form.get("vendor_to") or [""])[0]),
                "vendor_cc": str((form.get("vendor_cc") or [""])[0]),
            }
            template = mailer.load_template()
            errors = save_default_recipients(
                mailer.TEMPLATE_PATH,
                template,
                values,
            )
            if errors:
                html = portal_html(
                    "입력 내용을 확인하세요.",
                    errors=errors,
                    posted_values=values,
                )
                self._write(html.encode("utf-8"), status=400)
                return
            PortalHandler.status_message = "기본 발송 설정을 저장했습니다."
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if path == "/action/save-mail-edits":
            payload = mailer.load_drafts_payload()
            template = mailer.load_template()
            draft_id = str((form.get("draft_id") or [""])[0])
            source_hash = str((form.get("source_hash") or [""])[0])
            scope = str((form.get("save_scope") or [""])[0])
            values = {
                field: str((form.get(field) or [""])[0])
                for field in EDITABLE_FIELDS
            }
            errors = save_editor_action(
                scope=scope,
                payload=payload,
                template=template,
                override_path=OVERRIDES_PATH,
                template_path=mailer.TEMPLATE_PATH,
                draft_id=draft_id,
                source_hash=source_hash,
                values=values,
            )
            if errors:
                html = render_mail_editor(
                    payload,
                    template,
                    load_overrides(OVERRIDES_PATH),
                    CSRF_TOKEN,
                    send_mode=load_automation_settings(AUTOMATION_SETTINGS_PATH)["send_mode"],
                    selected_id=draft_id,
                    notice="입력 내용을 확인하세요.",
                    errors=errors,
                    posted_values=values,
                )
                self._write(
                    html.encode("utf-8"),
                    status=403 if "form" in errors else 400,
                )
                return
            target = "/confirm-send?" + urlencode({"draft": draft_id, "saved": scope})
            self.send_response(303)
            self.send_header("Location", target)
            self.end_headers()
            return
        if path == "/action/sync":
            ok, message = sync_once()
        elif path == "/action/send":
            supplied_digest = str((form.get("draft_digest") or [""])[0])
            current_payload = mailer.load_drafts_payload()
            current_payload = effective_payload(
                current_payload,
                mailer.load_template(),
                load_overrides(OVERRIDES_PATH),
            )
            current_digest = draft_batch_digest(current_payload)
            if not validate_send_request(CSRF_TOKEN, supplied_token, current_digest, supplied_digest):
                self._write(
                    "초안이 변경되었거나 승인 정보가 만료되었습니다. 내용을 다시 확인하세요.".encode("utf-8"),
                    "text/plain; charset=utf-8",
                    403,
                )
                return
            ok, message = send_once(current_payload)
        else:
            ok, message = False, "알 수 없는 요청입니다."
        PortalHandler.status_message = message if ok else f"오류: {message}"
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        return


def monitor_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        ok, message = sync_once()
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        PortalHandler.status_message = f"[{started_at}] {message}" if ok else f"[{started_at}] 오류: {message}"
        stop_event.wait(INTERVAL)


def main() -> int:
    stop_event = threading.Event()
    worker = threading.Thread(target=monitor_loop, args=(stop_event,), daemon=True)
    worker.start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), PortalHandler)
    print(f"포털 주소: http://127.0.0.1:{PORT}")
    print(f"백그라운드에서 {INTERVAL}초마다 메일을 확인합니다. 종료하려면 Ctrl+C를 누르세요.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("포털을 종료합니다.")
    finally:
        stop_event.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
