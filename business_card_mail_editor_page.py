from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping

from business_card_mail_editor import (
    EDITABLE_FIELDS,
    _rebuild_body,
    effective_payload,
    values_for_draft,
)
from business_card_portal_security import draft_batch_digest


def _display(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "-"


def _protected_details(draft: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for item in draft.get("requests") or []:
        request = item.get("request") or {}
        rows.append(
            "<tr>"
            f"<td>{escape(_display(request.get('employee_name')))}</td>"
            f"<td>{escape(_display(request.get('company_name')))}</td>"
            f"<td>{escape(_display(request.get('department')))}</td>"
            f"<td>{escape(_display(request.get('title')))}</td>"
            "</tr>"
        )
    body = "".join(rows) or "<tr><td colspan='4'>표시할 신청자 정보가 없습니다.</td></tr>"
    return (
        '<div class="protected-box" data-protected="order-details">'
        '<div class="protected-heading"><span>자동 생성 발주 정보</span>'
        '<span class="lock-label">수정 불가</span></div>'
        '<div class="table-scroll"><table><thead><tr>'
        '<th>이름</th><th>사업장</th><th>부서</th><th>직위</th>'
        f"</tr></thead><tbody>{body}</tbody></table></div></div>"
    )


def _field_error(errors: Mapping[str, str], field: str) -> str:
    message = errors.get(field)
    return f'<p class="field-error">{escape(str(message))}</p>' if message else ""


def mail_editor_send_mode_summary(send_mode: str) -> tuple[str, str, str, str]:
    if send_mode == "automatic":
        return ("automatic", "\uc790\ub3d9 \ubc1c\uc1a1 \uc911", "\uba85\ud568 \uc694\uccad\uc11c\ub294 \uac80\uc99d \ud6c4 \uc989\uc2dc \ubc1c\uc1a1\ud569\ub2c8\ub2e4.", "warning")
    return ("manual", "\uc9c1\uc811 \ud655\uc778 \uc911", "\ucd5c\uc885 \ud655\uc778 \ud6c4 \ubc1c\uc1a1\ud569\ub2c8\ub2e4.", "success")


def render_mail_editor_page(
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
    effective = effective_payload(payload, template, overrides)
    ready = [item for item in effective.get("drafts") or [] if item.get("status") == "ready"]
    ready_ids = {str(item.get("draft_id") or "") for item in ready}
    active_id = selected_id if selected_id in ready_ids else (
        str(ready[0].get("draft_id") or "") if ready else ""
    )
    error_map = dict(errors or {})
    mode, mode_label, mode_explanation, mode_tone = mail_editor_send_mode_summary(send_mode)
    navigation: list[str] = []
    forms: list[str] = []
    previews: list[str] = []

    for index, draft in enumerate(ready, start=1):
        draft_id = str(draft.get("draft_id") or "")
        values = dict(draft.get("editor_values") or values_for_draft(draft, template))
        if draft_id == active_id and posted_values:
            values.update({field: str(posted_values.get(field) or "") for field in EDITABLE_FIELDS})
        if not str(draft.get("html_body") or ""):
            _rebuild_body(draft, template, values)
        is_active = draft_id == active_id
        source_name = Path(str(draft.get("source_file") or "")).name or f"발주 메일 {index}"
        saved_label = "수정 저장됨" if draft.get("has_override") else "기본 초안"
        navigation.append(
            f'<button type="button" class="mail-item{" active" if is_active else ""}" '
            f'data-select-draft="{escape(draft_id, quote=True)}">'
            f'<span class="queue-no">MAIL {index:02d}</span><strong>{escape(source_name)}</strong>'
            f'<span>{escape(str(draft.get("vendor_to") or "미설정"))}</span>'
            f'<small>{escape(str(draft.get("request_count") or 0))}명 · {saved_label}</small></button>'
        )
        visible_errors = error_map if is_active else {}
        forms.append(
            f'<form class="draft-editor-form" data-draft-form="{escape(draft_id, quote=True)}" '
            f'method="post" action="/action/save-mail-edits" style="{"" if is_active else "display:none"}">'
            f'<input type="hidden" name="csrf_token" value="{escape(csrf_token, quote=True)}">'
            f'<input type="hidden" name="draft_id" value="{escape(draft_id, quote=True)}">'
            f'<input type="hidden" name="source_hash" value="{escape(str(draft.get("source_hash") or ""), quote=True)}">'
            '<div class="section-head"><div><span class="eyebrow">MAIL COMPOSITION</span>'
            '<h2>발송 문구 편집</h2></div><span class="safe-chip">텍스트만 입력</span></div>'
            '<div class="field-grid">'
            f'<label>수신<span>필수</span></label><div><input data-live="to" name="vendor_to" value="{escape(values["vendor_to"], quote=True)}">{_field_error(visible_errors, "vendor_to")}</div>'
            f'<label>참조<span>선택</span></label><div><input data-live="cc" name="vendor_cc" value="{escape(values["vendor_cc"], quote=True)}">{_field_error(visible_errors, "vendor_cc")}</div>'
            f'<label>제목<span>개별</span></label><div><input data-live="subject" name="subject" value="{escape(values["subject"], quote=True)}">{_field_error(visible_errors, "subject")}</div>'
            '</div><div class="rule"></div>'
            '<label class="copy-label">인사말</label>'
            f'<textarea data-live="greeting" name="greeting_text" rows="2">{escape(values["greeting_text"])}</textarea>'
            '<label class="copy-label">요청 문구</label>'
            f'<textarea data-live="request" name="request_text" rows="4">{escape(values["request_text"])}</textarea>'
            f'{_protected_details(draft)}'
            '<label class="copy-label">맺음말</label>'
            f'<textarea data-live="closing" name="closing_text" rows="3">{escape(values["closing_text"])}</textarea>'
            '<div class="save-actions">'
            '<button class="button ghost" name="save_scope" value="defaults">기본값으로 저장</button>'
            '<button class="button bronze" name="save_scope" value="all">수신·참조·문구 전체 적용</button>'
            '<button class="button primary" name="save_scope" value="one">이번 발송에만 저장</button>'
            '</div></form>'
        )
        attachments = "".join(
            f'<li>{escape(Path(str(path)).name)}</li>'
            for path in draft.get("attachment_paths") or []
        ) or "<li>첨부파일 없음</li>"
        previews.append(
            f'<template data-preview-template="{escape(draft_id, quote=True)}">'
            f'{draft.get("html_body") or ""}</template>'
            f'<div data-attachments="{escape(draft_id, quote=True)}" hidden><ul>{attachments}</ul></div>'
        )

    digest = draft_batch_digest(effective)
    notice_html = f'<div class="notice">{escape(notice)}</div>' if notice else ""
    if ready:
        workspace = (
            f'<aside class="mail-list"><div class="panel-title">메일 목록 '
            f'<strong>{len(ready)}</strong></div>{"".join(navigation)}</aside>'
            f'<section class="editor-panel">{"".join(forms)}</section>'
        )
        send_action = (
            '<div class="send-blocked">입력 오류를 수정하고 저장하면 최종 발송할 수 있습니다.</div>'
            if error_map
            else '<form method="post" action="/action/send">'
            f'<input type="hidden" name="csrf_token" value="{escape(csrf_token, quote=True)}">'
            f'<input type="hidden" name="draft_digest" value="{escape(digest, quote=True)}">'
            '<button type="submit" class="final-send-button">확인했고 최종 발송합니다</button></form>'
        )
        preview = (
            '<div class="preview-meta"><p><span>수신</span><strong data-preview-to></strong></p>'
            '<p><span>참조</span><strong data-preview-cc></strong></p>'
            '<p><span>제목</span><strong data-preview-subject></strong></p></div>'
            '<iframe title="실제 발송 메일 미리보기" class="mail-preview-frame"></iframe>'
            '<div class="attachment-preview"><span>첨부파일</span><div data-preview-attachments></div></div>'
            '<div class="send-warning">외부 업체로 실제 발송됩니다. 수신자와 첨부파일을 다시 확인하세요.</div>'
            f'{send_action}'
        )
    else:
        workspace = (
            '<section class="empty-state"><span>READY QUEUE / 0</span>'
            '<h2>현재 발송 준비된 메일이 없습니다.</h2>'
            '<p>대시보드에서 신청서 처리 상태를 확인한 뒤 다시 열어주세요.</p>'
            '<a href="/dashboard">대시보드로 돌아가기</a></section>'
        )
        preview = '<div class="preview-empty">발송 가능한 초안이 생기면 실제 메일 미리보기가 표시됩니다.</div>'

    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>메일 편집 및 발송 | K Group 명함 자동발주 시스템</title>
<style>
:root{{--canvas:#F3EFE7;--surface:#FFFDF7;--ink:#282A25;--muted:#716F67;--green:#173F35;--green2:#245B4B;--bronze:#B77945;--border:#DDD6C8;--success:#176B50;--warning:#97520F;--error:#A33E36}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--canvas);color:var(--ink);font-family:"Malgun Gothic",Arial,sans-serif}}button,input,textarea{{font:inherit}}button{{cursor:pointer}}.topbar{{min-height:72px;background:var(--surface);border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;padding:14px 28px;gap:20px}}.brand{{display:flex;align-items:center;gap:18px}}.back{{color:var(--muted);text-decoration:none;font-size:12px;font-weight:700}}.brand h1{{font-size:19px;margin:0;color:var(--green)}}.status{{display:flex;align-items:center;gap:12px;font-size:12px;color:var(--muted)}}.status strong{{color:var(--green);font-size:15px}}.mode-status{{display:flex;align-items:center;gap:7px;max-width:350px;line-height:1.35}}.mode-badge{{flex:none;padding:5px 8px;border-radius:999px;font-size:10px;font-weight:900;white-space:nowrap}}.mode-badge--success{{background:#DCEEE5;color:var(--success)}}.mode-badge--warning{{background:#F7E2C3;color:var(--warning)}}.safe-chip{{background:#DCEEE5;color:var(--success);padding:6px 10px;border-radius:999px;font-size:11px;font-weight:800}}.notice{{margin:14px 24px 0;padding:12px 16px;background:#F7E2C3;color:var(--warning);border:1px solid #E7C997;border-radius:10px;font-size:13px}}.shell{{display:grid;grid-template-columns:minmax(760px,1fr) 410px;min-height:calc(100vh - 72px)}}.workspace{{display:grid;grid-template-columns:250px minmax(510px,1fr);min-width:0}}.mail-list{{background:var(--surface);border-right:1px solid var(--border);padding:18px 12px}}.panel-title{{padding:0 8px 14px;color:var(--muted);font-size:12px;font-weight:800}}.panel-title strong{{float:right;color:var(--green)}}.mail-item{{display:block;width:100%;border:1px solid var(--border);background:transparent;text-align:left;border-radius:12px;padding:14px;margin-bottom:9px;color:var(--ink)}}.mail-item span,.mail-item small,.mail-item strong{{display:block}}.mail-item strong{{margin:6px 0;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.mail-item span{{color:var(--muted);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.mail-item small{{margin-top:10px;padding-top:9px;border-top:1px solid var(--border);font-size:10px;color:var(--muted)}}.mail-item .queue-no{{font-size:9px;letter-spacing:.1em;font-weight:900}}.mail-item.active{{background:var(--green);border-color:var(--green);color:var(--surface)}}.mail-item.active span,.mail-item.active small{{color:#DCE6E1}}.editor-panel{{padding:28px;min-width:0;overflow:auto}}.draft-editor-form{{max-width:780px;margin:0 auto;background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px}}.section-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}}.eyebrow{{font-size:10px;color:var(--bronze);font-weight:900;letter-spacing:.13em}}.section-head h2{{margin:5px 0 0;font-size:21px}}.field-grid{{display:grid;grid-template-columns:80px 1fr;gap:14px 16px;align-items:start}}.field-grid>label{{padding-top:11px;font-size:12px;font-weight:800}}.field-grid>label span{{display:block;margin-top:2px;color:var(--muted);font-size:9px;font-weight:500}}input,textarea{{width:100%;border:1px solid var(--border);background:#FFFEFA;border-radius:9px;padding:11px 12px;color:var(--ink)}}input:focus,textarea:focus{{outline:2px solid #B9C8C2;border-color:var(--green)}}textarea{{resize:vertical;line-height:1.65}}.field-error{{margin:5px 0 0;color:var(--error);font-size:11px}}.rule{{height:1px;background:var(--border);margin:23px 0}}.copy-label{{display:block;margin:17px 0 7px;font-size:11px;font-weight:900;color:var(--muted)}}.protected-box{{margin:20px 0;border:1px solid var(--border);background:#F7F4EC;border-radius:11px;padding:14px}}.protected-heading{{display:flex;justify-content:space-between;margin-bottom:11px;font-size:11px;font-weight:900}}.lock-label{{color:var(--warning)}}.table-scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:11px}}th,td{{border-bottom:1px solid var(--border);padding:8px;text-align:left;white-space:nowrap}}th{{color:var(--muted)}}.save-actions{{display:flex;justify-content:flex-end;gap:9px;margin-top:24px;padding-top:18px;border-top:1px solid var(--border);flex-wrap:wrap}}.button,.final-send-button{{border:1px solid transparent;border-radius:9px;padding:11px 14px;font-size:11px;font-weight:900}}.button.ghost{{background:transparent;border-color:var(--border);color:var(--muted)}}.button.bronze{{background:#FFF7EF;border-color:var(--bronze);color:#8A522B}}.button.primary,.final-send-button{{background:var(--green);color:white}}.preview-panel{{background:var(--surface);border-left:1px solid var(--border);padding:20px;min-width:0}}.preview-panel>h2{{margin:0 0 16px;font-size:12px;color:var(--muted);letter-spacing:.1em}}.preview-meta{{border:1px solid var(--border);border-bottom:0;border-radius:12px 12px 0 0;padding:14px;background:white}}.preview-meta p{{display:grid;grid-template-columns:48px 1fr;margin:5px 0;font-size:11px}}.preview-meta span{{color:var(--muted);font-weight:800}}.preview-meta strong{{overflow-wrap:anywhere}}.mail-preview-frame{{display:block;width:100%;height:430px;border:1px solid var(--border);background:white}}.attachment-preview{{border:1px solid var(--border);border-top:0;padding:13px;background:white;font-size:11px}}.attachment-preview>span{{font-weight:900;color:var(--muted)}}.attachment-preview ul{{margin:7px 0 0;padding-left:18px}}.send-warning{{margin-top:14px;padding:12px;background:#F6DEDB;color:var(--error);border:1px solid #E8BEB8;border-radius:9px;font-size:11px;line-height:1.5}}.final-send-button{{width:100%;margin-top:10px;padding:14px}}.empty-state{{grid-column:1/-1;margin:60px auto;max-width:540px;text-align:center;padding:42px;background:var(--surface);border:1px solid var(--border);border-radius:16px}}.empty-state span{{color:var(--bronze);font-size:10px;font-weight:900}}.empty-state h2{{font-size:23px}}.empty-state p,.preview-empty{{color:var(--muted);line-height:1.7}}.empty-state a{{display:inline-block;margin-top:10px;color:white;background:var(--green);padding:11px 15px;border-radius:8px;text-decoration:none;font-size:12px;font-weight:800}}
@media(max-width:1180px){{.shell{{grid-template-columns:1fr}}.preview-panel{{border-left:0;border-top:1px solid var(--border)}}.mail-preview-frame{{height:360px}}}}@media(max-width:760px){{.topbar{{align-items:flex-start;padding:14px 16px}}.brand{{display:block}}.back{{display:block;margin-bottom:8px}}.status{{align-items:flex-start;flex-wrap:wrap;justify-content:flex-end}}.mode-status{{max-width:100%;flex-basis:100%}}.workspace{{grid-template-columns:1fr}}.mail-list{{border-right:0;border-bottom:1px solid var(--border);display:flex;overflow:auto;gap:8px}}.panel-title{{display:none}}.mail-item{{min-width:220px;margin:0}}.editor-panel{{padding:14px}}.draft-editor-form{{padding:17px}}.field-grid{{grid-template-columns:1fr;gap:7px}}.field-grid>label{{padding-top:7px}}.field-grid>label span{{display:inline;margin-left:7px}}.save-actions{{display:grid}}.button{{width:100%}}.preview-panel{{padding:14px}}}}
</style></head><body>
<header class="topbar"><div class="brand"><a class="back" href="/dashboard">← 대시보드</a><h1>메일 편집 및 발송</h1></div><div class="status"><span class="mode-status" data-send-mode="{mode}"><span class="mode-badge mode-badge--{mode_tone}">{escape(mode_label)}</span><span>{escape(mode_explanation)}</span></span><span class="safe-chip">\ubc1c\uc1a1 \uc804 \uac80\uc99d \ud65c\uc131</span><span>\uc900\ube44\ub41c \uba54\uc77c <strong>{len(ready)}</strong>\uac74</span></div></header>
{notice_html}<div class="shell"><main class="workspace">{workspace}</main><aside class="preview-panel"><h2>FINAL MAIL PREVIEW</h2>{preview}</aside></div>
{"".join(previews)}
<script>
const forms=[...document.querySelectorAll('[data-draft-form]')];const items=[...document.querySelectorAll('[data-select-draft]')];const frame=document.querySelector('.mail-preview-frame');let active='';
function fillLines(container,text){{if(!container)return;container.replaceChildren();String(text||'').split(/\\r?\\n/).forEach(line=>{{const p=document.createElement('p');p.style.margin='0 0 8px 0';p.textContent=line||' ';container.appendChild(p);}})}}
function refresh(form){{if(!form||!frame)return;document.querySelector('[data-preview-to]').textContent=form.querySelector('[data-live="to"]').value||'-';document.querySelector('[data-preview-cc]').textContent=form.querySelector('[data-live="cc"]').value||'-';document.querySelector('[data-preview-subject]').textContent=form.querySelector('[data-live="subject"]').value||'-';const source=document.querySelector('[data-preview-template="'+active+'"]');frame.onload=()=>{{const doc=frame.contentDocument;fillLines(doc.querySelector('[data-mail-section="intro"]'),form.querySelector('[data-live="greeting"]').value+'\\n'+form.querySelector('[data-live="request"]').value);fillLines(doc.querySelector('[data-mail-section="closing"]'),form.querySelector('[data-live="closing"]').value);}};frame.srcdoc=source?source.innerHTML:'';const files=document.querySelector('[data-attachments="'+active+'"]');document.querySelector('[data-preview-attachments]').innerHTML=files?files.innerHTML:'';}}
function selectDraft(id){{active=id;forms.forEach(form=>form.style.display=form.dataset.draftForm===id?'':'none');items.forEach(item=>item.classList.toggle('active',item.dataset.selectDraft===id));refresh(forms.find(form=>form.dataset.draftForm===id));}}
items.forEach(item=>item.addEventListener('click',()=>selectDraft(item.dataset.selectDraft)));forms.forEach(form=>form.querySelectorAll('input[data-live],textarea[data-live]').forEach(input=>input.addEventListener('input',()=>refresh(form))));if(forms.length)selectDraft({active_id!r});
</script></body></html>'''
