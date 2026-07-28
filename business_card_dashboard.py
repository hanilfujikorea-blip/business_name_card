"""Presentation helpers for the business-card operations dashboard.

This module deliberately owns only dashboard presentation. The mailer keeps data
collection and sending behavior, while each history table can evolve independently.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping


PALETTE = {
    "canvas": "#F3EFE7",
    "surface": "#FFFDF7",
    "ink": "#282A25",
    "muted": "#716F67",
    "green": "#173F35",
    "green_2": "#245B4B",
    "bronze": "#B77945",
    "border": "#DDD6C8",
    "success_bg": "#DCEEE5",
    "success_fg": "#176B50",
    "warning_bg": "#F7E2C3",
    "warning_fg": "#97520F",
    "error_bg": "#F6DEDB",
    "error_fg": "#A33E36",
}


def _plain(value: Any, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _safe(value: Any, fallback: str = "-") -> str:
    return escape(_plain(value, fallback))


def _count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def field_label(field: str, template: Mapping[str, Any]) -> str:
    labels = template.get("field_labels") or {}
    if isinstance(labels, Mapping):
        label = _plain(labels.get(field), "")
        if label:
            return label
    return field


def cleanup_history_note(note: Any, fallback: str) -> str:
    text = _plain(note, "")
    if not text or text.count("?") >= 2:
        return fallback
    return text


def summarize_send_history(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    history = state.get("send_history") or []
    if not isinstance(history, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in history[:20]:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["note"] = cleanup_history_note(row.get("note"), "\ubc1c\uc8fc \ucc98\ub9ac \uc774\ub825")
        normalized.append(row)
    return normalized


def summarize_import_history(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    history = state.get("import_history") or []
    if not isinstance(history, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in history[:20]:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["note"] = cleanup_history_note(row.get("note"), "\uba54\uc77c \uc218\uc9d1 \uc774\ub825")
        normalized.append(row)
    return normalized


def dashboard_review_count(payload: Mapping[str, Any]) -> int:
    return _count(payload.get("pending_count")) + len(payload.get("parse_errors") or [])


def dashboard_status_summary(payload: Mapping[str, Any]) -> tuple[str, str, str]:
    ready_count = _count(payload.get("ready_count"))
    review_count = dashboard_review_count(payload)
    if ready_count:
        return (
            "ready",
            f"\ubc1c\uc1a1\uc744 \uae30\ub2e4\ub9ac\ub294 \uc2e0\uccad\uc774 {ready_count}\uac74 \uc788\uc2b5\ub2c8\ub2e4",
            "\ubc1c\uc1a1 \uc804 \uc218\uc2e0\uc778\uacfc \ucca8\ubd80\ud30c\uc77c\uc744 \ud55c \ubc88 \ub354 \ud655\uc778\ud558\uc138\uc694.",
        )
    if review_count:
        return (
            "warning",
            f"\ud655\uc778\uc774 \ud544\uc694\ud55c \uc2e0\uccad\uc774 {review_count}\uac74 \uc788\uc2b5\ub2c8\ub2e4",
            "\ub204\ub77d \ud56d\ubaa9\uacfc \ud30c\uc2f1 \uc624\ub958\ub97c \uc815\ub9ac\ud558\uba74 \ubc1c\uc1a1 \uc900\ube44\ub85c \uc774\ub3d9\ud569\ub2c8\ub2e4.",
        )
    return (
        "quiet",
        "\ud604\uc7ac \ucc98\ub9ac\ud560 \ubc1c\uc8fc\uac00 \uc5c6\uc2b5\ub2c8\ub2e4",
        "\uc0c8 \uba54\uc77c\uc744 \uc218\uc9d1\ud558\uba74 \uc5ec\uae30\uc5d0 \uc6b0\uc120\uc21c\uc704\uac00 \ud45c\uc2dc\ub429\ub2c8\ub2e4.",
    )


def _badge(label: str, tone: str) -> str:
    return f'<span class="badge badge--{tone}">{escape(label)}</span>'


def dashboard_send_mode_summary(send_mode: str) -> tuple[str, str, str, str]:
    if send_mode == "automatic":
        return ("automatic", "\uc790\ub3d9 \ubc1c\uc1a1 \uc911", "\uba85\ud568 \uc694\uccad\uc11c\ub294 \uac80\uc99d \ud6c4 \uc989\uc2dc \ubc1c\uc1a1\ud569\ub2c8\ub2e4.", "warning")
    return ("manual", "\uc9c1\uc811 \ud655\uc778 \uc911", "\ucd5c\uc885 \ud655\uc778 \ud6c4 \ubc1c\uc1a1\ud569\ub2c8\ub2e4.", "success")


def _render_table(
    headers: Iterable[str],
    rows: Iterable[Iterable[str]],
    empty_message: str,
    accessible_label: str,
) -> str:
    row_list = list(rows)
    if not row_list:
        return f'<div class="empty-state">{escape(empty_message)}</div>'
    head = "".join(f"<th scope=\"col\">{escape(header)}</th>" for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in row_list
    )
    return (
        f'<div class="table-scroll" role="region" aria-label="{escape(accessible_label)}" tabindex="0">'
        f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
    )


def _history_card(
    *,
    section: str,
    title: str,
    description: str,
    table_html: str,
    open_by_default: bool = False,
) -> str:
    open_attr = " open" if open_by_default else ""
    return (
        f'<details class="history-card" data-section="{section}"{open_attr}>'
        '<summary>'
        '<span class="summary-copy">'
        f'<strong>{escape(title)}</strong><span>{escape(description)}</span>'
        '</span>'
        '<span class="summary-action" aria-hidden="true">\uc5f4\uae30</span>'
        '</summary>'
        f'<div class="history-body">{table_html}</div>'
        '</details>'
    )


def render_mail_history_table(rows: list[dict[str, Any]]) -> str:
    rendered = [
        (
            _safe(item.get("fetched_at")),
            _safe(item.get("mail_scan_count"), "0"),
            _safe(item.get("imported_count"), "0"),
            _safe(item.get("skipped_count"), "0"),
            _safe(item.get("note")),
        )
        for item in rows
    ]
    table = _render_table(
        ["\uc218\uc9d1 \uc2dc\uac01", "\ud655\uc778 \uba54\uc77c \uc218", "\uac00\uc838\uc628 \uc218", "\uac74\ub108\ub700", "\uba54\ubaa8"],
        rendered,
        "\uc544\uc9c1 \uc218\uc9d1 \uc774\ub825\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.",
        "\uba54\uc77c \uc218\uc9d1 \uc774\ub825 \ud45c",
    )
    return _history_card(
        section="mail-history",
        title="\uba54\uc77c \uc218\uc9d1 \uc774\ub825",
        description="\ud655\uc778\ud55c \uba54\uc77c\uacfc \uc0c8\ub85c \uac00\uc838\uc628 \uc2e0\uccad\uc11c\ub97c \ud68c\ucc28\ubcc4\ub85c \ubcf4\uc5ec\uc90d\ub2c8\ub2e4.",
        table_html=table,
    )


def render_send_history_table(rows: list[dict[str, Any]]) -> str:
    rendered = [
        (
            _safe(item.get("sent_at")),
            _safe(item.get("success_count"), "0"),
            _safe(item.get("fail_count"), "0"),
            _safe(item.get("total_count"), "0"),
            _safe(item.get("note")),
        )
        for item in rows
    ]
    table = _render_table(
        ["\ubc1c\uc1a1 \uc2dc\uac01", "\uc131\uacf5", "\uc2e4\ud328", "\uc804\uccb4", "\uba54\ubaa8"],
        rendered,
        "\uc544\uc9c1 \ubc1c\uc1a1 \uc774\ub825\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.",
        "\ubc1c\uc1a1 \uc774\ub825 \ud45c",
    )
    return _history_card(
        section="send-history",
        title="\ubc1c\uc1a1 \uc774\ub825",
        description="\uc5c5\uccb4 \ubc1c\uc8fc \uba54\uc77c\uc774 \uc5b8\uc81c \uba87 \uac74 \ucc98\ub9ac\ub410\ub294\uc9c0 \ubcf4\uc5ec\uc90d\ub2c8\ub2e4.",
        table_html=table,
    )


def render_latest_send_results_table(
    rows: list[dict[str, Any]], *, open_by_default: bool = False
) -> str:
    rendered = []
    for item in rows:
        ok = bool(item.get("ok"))
        rendered.append(
            (
                _safe(item.get("sent_at")),
                _safe(item.get("subject")),
                _badge("\uc131\uacf5" if ok else "\uc2e4\ud328", "success" if ok else "error"),
                _safe(item.get("message") or item.get("reason")),
            )
        )
    table = _render_table(
        ["\uc2dc\uac04", "\uc81c\ubaa9", "\uacb0\uacfc", "\uba54\uc2dc\uc9c0"],
        rendered,
        "\ucd5c\uadfc \ubc1c\uc1a1 \uacb0\uacfc\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.",
        "\ucd5c\uadfc \ubc1c\uc1a1 \uacb0\uacfc \uc0c1\uc138 \ud45c",
    )
    return _history_card(
        section="latest-send-results",
        title="\ucd5c\uadfc \ubc1c\uc1a1 \uacb0\uacfc \uc0c1\uc138",
        description="\uba54\uc77c\ubcc4 \uc81c\ubaa9, \uc131\uacf5 \uc5ec\ubd80, \uc751\ub2f5 \uba54\uc2dc\uc9c0\ub97c \ud655\uc778\ud569\ub2c8\ub2e4.",
        table_html=table,
        open_by_default=open_by_default,
    )


def _render_priority_section(payload: Mapping[str, Any], template: Mapping[str, Any]) -> str:
    cards: list[str] = []
    for item in payload.get("drafts") or []:
        status = str(item.get("status") or "pending")
        is_ready = status == "ready"
        missing = [field_label(str(field), template) for field in item.get("missing_fields") or []]
        metadata = [
            f"\uc2e0\uccad {_safe(item.get('request_count'), '0')}\uba85",
            f"\uc2e0\uccad\uc77c {_safe(item.get('request_date'))}",
            f"\uc218\uc2e0 {_safe(item.get('vendor_to'))}",
        ]
        if missing:
            metadata.append("\ub204\ub77d " + escape(", ".join(missing)))
        cards.append(
            f'<article class="work-item" data-tone="{"ready" if is_ready else "warning"}">'
            '<div class="work-marker" aria-hidden="true"></div>'
            '<div class="work-copy">'
            f'<div class="work-title"><strong>{_safe(Path(str(item.get("source_file") or "")).name)}</strong>'
            f'{_badge("\ubc1c\uc1a1 \uc900\ube44" if is_ready else "\ud655\uc778 \ud544\uc694", "success" if is_ready else "warning")}</div>'
            f'<p>{" · ".join(metadata)}</p>'
            '</div></article>'
        )

    for item in payload.get("parse_errors") or []:
        cards.append(
            '<article class="work-item" data-tone="error">'
            '<div class="work-marker" aria-hidden="true"></div><div class="work-copy">'
            f'<div class="work-title"><strong>{_safe(Path(str(item.get("file") or "")).name)}</strong>{_badge("\ud30c\uc2f1 \uc624\ub958", "error")}</div>'
            f'<p>{_safe(item.get("error"), "\ud30c\uc77c \ub0b4\uc6a9\uc744 \ud655\uc778\ud558\uc138\uc694.")}</p>'
            '</div></article>'
        )

    actionable_count = len(cards)
    if not cards:
        cards.append('<div class="empty-state">\ud604\uc7ac \uc6b0\uc120 \ucc98\ub9ac\ud560 \ud56d\ubaa9\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.</div>')
    return (
        '<section class="panel priority-panel" data-section="priority">'
        '<div class="section-heading"><div><span class="section-kicker">TODAY</span>'
        '<h2>\uc6b0\uc120 \ucc98\ub9ac \ud56d\ubaa9</h2></div>'
        '<span class="section-count">' + str(actionable_count) + '\uac74</span></div>'
        '<p class="section-description">\ubc1c\uc1a1 \uc900\ube44\uc640 \ud655\uc778 \ud544\uc694 \ud56d\ubaa9\uc744 \ucc98\ub9ac \uc21c\uc11c\ub300\ub85c \ubaa8\uc558\uc2b5\ub2c8\ub2e4.</p>'
        '<div class="work-list">' + "".join(cards) + '</div></section>'
    )


def _render_collection_panel(fetch_result: Mapping[str, Any]) -> str:
    results = fetch_result.get("results") or []
    rows = []
    for item in results[:20]:
        imported = item.get("status") == "imported"
        filenames = ", ".join(Path(str(path)).name for path in item.get("saved_files") or [])
        rows.append(
            (
                _safe(item.get("subject")),
                _safe(item.get("sender")),
                _badge("\uac00\uc838\uc634" if imported else "\uac74\ub108\ub700", "success" if imported else "neutral"),
                _safe(filenames),
            )
        )
    table = _render_table(
        ["\uba54\uc77c \uc81c\ubaa9", "\ubcf4\ub0b8 \uc0ac\ub78c", "\uc0c1\ud0dc", "\uc800\uc7a5 \ud30c\uc77c"],
        rows,
        "\uc774\ubc88 \ud68c\ucc28\uc5d0 \uc0c8\ub85c \uac00\uc838\uc628 \uba54\uc77c\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.",
        "\uc774\ubc88 \ud68c\ucc28 \uba54\uc77c \uc218\uc9d1 \uacb0\uacfc",
    )
    return (
        '<section class="panel collection-panel" data-section="collection">'
        '<div class="section-heading"><div><span class="section-kicker">LATEST IMPORT</span>'
        '<h2>\uc774\ubc88 \ud68c\ucc28 \uba54\uc77c \uc218\uc9d1</h2></div>'
        f'<span class="section-count">{_count(fetch_result.get("imported_count"))}\uac74</span></div>'
        '<p class="section-description">\uc0c8\ub85c \ud655\uc778\ud55c \uba54\uc77c\uacfc \uc800\uc7a5\ub41c \ucca8\ubd80\ud30c\uc77c\uc785\ub2c8\ub2e4.</p>'
        f'{table}</section>'
    )


def _metric(label: str, value: Any, note: str, tone: str = "default") -> str:
    return (
        f'<article class="metric" data-tone="{tone}">'
        f'<span>{escape(label)}</span><strong>{_count(value)}</strong><small>{escape(note)}</small>'
        '</article>'
    )


def render_dashboard_html(
    payload: dict[str, Any],
    template: dict[str, Any],
    state: dict[str, Any],
    send_result: dict[str, Any],
    fetch_result: dict[str, Any],
    send_mode: str = "manual",
) -> str:
    mode, mode_label, mode_explanation, mode_tone = dashboard_send_mode_summary(send_mode)
    tone, status_title, status_note = dashboard_status_summary(payload)
    ready_count = _count(payload.get("ready_count"))
    review_count = dashboard_review_count(payload)
    success_count = _count(send_result.get("success_count"))
    fail_count = _count(send_result.get("fail_count"))
    sent_hashes = state.get("sent_hashes") or {}
    sent_total = len(sent_hashes) if isinstance(sent_hashes, Mapping) else 0
    import_history = summarize_import_history(state)
    send_history = summarize_send_history(state)
    workflow_final_step = (
        '<li><strong>\uc790\ub3d9 \ubc1c\uc1a1</strong>\uac80\uc99d\uc744 \ud1b5\uacfc\ud55c \uc0c8 \uba85\ud568 \uc2e0\uccad\uc11c\ub97c \uc989\uc2dc \ubc1c\uc1a1\ud569\ub2c8\ub2e4.</li>'
        if mode == "automatic"
        else '<li><strong>\uc0ac\ub78c\uc774 \ucd5c\uc885 \uac80\ud1a0</strong>\ud3ec\ud138\uc5d0\uc11c \ub0b4\uc6a9\uc744 \ud655\uc778\ud55c \ub4a4\uc5d0\ub9cc \ubc1c\uc1a1\ud569\ub2c8\ub2e4.</li>'
    )

    styles = f"""
    :root{{--canvas:{PALETTE['canvas']};--surface:{PALETTE['surface']};--ink:{PALETTE['ink']};--muted:{PALETTE['muted']};--green:{PALETTE['green']};--green-2:{PALETTE['green_2']};--bronze:{PALETTE['bronze']};--line:{PALETTE['border']};--success-bg:{PALETTE['success_bg']};--success-fg:{PALETTE['success_fg']};--warning-bg:{PALETTE['warning_bg']};--warning-fg:{PALETTE['warning_fg']};--error-bg:{PALETTE['error_bg']};--error-fg:{PALETTE['error_fg']};--shadow:0 18px 50px rgba(40,42,37,.08)}}
    *{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--canvas);color:var(--ink);font-family:Pretendard,"Noto Sans KR","Malgun Gothic",system-ui,sans-serif;font-size:16px;line-height:1.6}}a{{color:inherit}}button,a,summary{{-webkit-tap-highlight-color:transparent}}:focus-visible{{outline:3px solid var(--bronze);outline-offset:3px;border-radius:6px}}
    .shell{{width:min(1440px,100%);margin:0 auto;min-height:100vh;padding:18px 28px 54px}}.topbar{{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:12px 2px 22px;border-bottom:1px solid rgba(40,42,37,.16)}}.brand{{display:flex;align-items:center;gap:12px;text-decoration:none;font-weight:850;letter-spacing:-.03em}}.brand-mark{{display:grid;place-items:center;width:36px;height:36px;border-radius:50%;background:var(--green);color:var(--surface);font-size:18px}}.brand-copy{{white-space:nowrap}}.brand-copy small{{display:block;color:var(--muted);font-size:12px;letter-spacing:.15em;font-weight:800}}.mode-status{{display:flex;align-items:center;gap:8px;max-width:390px;color:var(--muted);font-size:13px;line-height:1.35}}.mode-status .badge{{flex:none}}.topnav{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}}.nav-link{{padding:9px 13px;text-decoration:none;color:var(--muted);font-size:14px;font-weight:750;border-radius:999px}}.nav-link:hover{{background:rgba(255,253,247,.75);color:var(--green)}}.nav-link--primary{{background:var(--green);color:#fff}}.nav-link--primary:hover{{background:var(--green-2);color:#fff}}
    .hero{{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(260px,.7fr);gap:22px;padding:52px 0 28px}}.hero-copy{{align-self:end}}.eyebrow,.section-kicker{{display:block;color:var(--bronze);font-size:12px;font-weight:900;letter-spacing:.16em}}.hero h1{{max-width:820px;margin:12px 0 16px;font-size:30px;line-height:1.03;letter-spacing:-.045em;font-weight:600}}.hero-description{{max-width:700px;margin:0;color:var(--muted);font-size:16px}}.hero-status{{align-self:stretch;display:flex;flex-direction:column;justify-content:space-between;min-height:238px;padding:24px;border-top:4px solid var(--green);background:var(--surface);box-shadow:var(--shadow)}}.hero-status[data-tone="warning"]{{border-color:var(--bronze)}}.hero-status[data-tone="quiet"]{{border-color:var(--line)}}.status-label{{font-size:12px;font-weight:900;letter-spacing:.14em;color:var(--muted)}}.hero-status strong{{display:block;margin:22px 0 12px;font-size:29px;line-height:1.2;font-weight:600}}.hero-status p{{margin:0;color:var(--muted);font-size:14px}}.status-meta{{padding-top:18px;margin-top:20px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:12px}}
    .primary-metrics{{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--ink);border-bottom:1px solid var(--line);background:var(--surface)}}.metric{{position:relative;min-width:0;padding:22px 24px;border-right:1px solid var(--line)}}.metric:last-child{{border-right:0}}.metric>span{{display:block;color:var(--muted);font-size:14px;font-weight:800}}.metric strong{{display:block;margin:4px 0 1px;font-size:38px;line-height:1;color:var(--green);font-weight:600}}.metric small{{color:var(--muted);font-size:13px}}.metric[data-tone="warning"] strong{{color:var(--warning-fg)}}.metric[data-tone="error"] strong{{color:var(--error-fg)}}
    .content-grid{{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(280px,.65fr);gap:22px;margin-top:22px}}.panel{{background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow);padding:24px}}.section-heading{{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}}.section-heading h2{{margin:5px 0 0;font-size:22px;line-height:1.15;font-weight:600;letter-spacing:-.025em}}.section-count{{flex:none;display:grid;place-items:center;min-width:48px;height:32px;border:1px solid var(--line);border-radius:999px;color:var(--green);font-size:12px;font-weight:850}}.section-description{{margin:10px 0 20px;color:var(--muted);font-size:14px}}.work-list{{display:grid;gap:10px}}.work-item{{display:grid;grid-template-columns:4px 1fr;gap:14px;padding:14px 15px 14px 0;border-top:1px solid var(--line)}}.work-item:first-child{{border-top:0}}.work-marker{{background:var(--green);border-radius:999px}}.work-item[data-tone="warning"] .work-marker{{background:var(--bronze)}}.work-item[data-tone="error"] .work-marker{{background:var(--error-fg)}}.work-item[data-tone="neutral"] .work-marker{{background:var(--line)}}.work-title{{display:flex;align-items:center;justify-content:space-between;gap:12px}}.work-title strong{{font-size:15px;overflow-wrap:anywhere}}.work-copy p{{margin:5px 0 0;color:var(--muted);font-size:14px;overflow-wrap:anywhere}}.badge{{display:inline-flex;align-items:center;white-space:nowrap;padding:4px 8px;border-radius:999px;font-size:12px;font-weight:850}}.badge--success{{background:var(--success-bg);color:var(--success-fg)}}.badge--warning{{background:var(--warning-bg);color:var(--warning-fg)}}.badge--error{{background:var(--error-bg);color:var(--error-fg)}}.badge--neutral{{background:#EEEAE1;color:var(--muted)}}
    .workflow-panel{{background:var(--green);color:#fff;box-shadow:none;border-color:var(--green)}}.workflow-panel .section-kicker{{color:#D8B38D}}.workflow-panel h2{{color:#fff}}.workflow-list{{counter-reset:step;list-style:none;margin:22px 0 0;padding:0}}.workflow-list li{{counter-increment:step;position:relative;padding:0 0 22px 46px;color:rgba(255,255,255,.74);font-size:14px}}.workflow-list li:last-child{{padding-bottom:0}}.workflow-list li::before{{content:counter(step,decimal-leading-zero);position:absolute;left:0;top:-2px;color:#D8B38D;font-size:18px}}.workflow-list li::after{{content:"";position:absolute;left:13px;top:24px;bottom:5px;width:1px;background:rgba(255,255,255,.18)}}.workflow-list li:last-child::after{{display:none}}.workflow-list strong{{display:block;margin-bottom:3px;color:#fff;font-size:15px}}
    .secondary-metrics{{display:grid;grid-template-columns:repeat(4,1fr);margin-top:22px;background:rgba(255,253,247,.55);border:1px solid var(--line)}}.secondary-metrics .metric{{box-shadow:none;background:transparent}}.secondary-metrics .metric strong{{font-size:30px}}
    .collection-panel{{margin-top:22px}}.table-scroll{{width:100%;overflow-x:auto;overscroll-behavior-inline:contain}}table{{width:100%;border-collapse:collapse;min-width:680px}}th,td{{padding:13px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:13px}}th{{color:var(--muted);font-size:12px;letter-spacing:.06em;text-transform:uppercase;background:#F8F5EE}}td{{overflow-wrap:anywhere}}tbody tr:hover{{background:#FAF7F0}}.empty-state{{padding:18px;border:1px dashed var(--line);background:#FAF7F0;color:var(--muted);font-size:14px;text-align:center}}
    .history-section{{margin-top:22px}}.history-heading{{display:flex;align-items:end;justify-content:space-between;margin:0 0 12px;padding:0 2px}}.history-heading h2{{margin:4px 0 0;font-size:24px;font-weight:600}}.history-heading p{{max-width:420px;margin:0;color:var(--muted);font-size:14px;text-align:right}}.history-stack{{display:grid;gap:10px}}.history-card{{background:var(--surface);border:1px solid var(--line)}}.history-card summary{{display:flex;align-items:center;justify-content:space-between;gap:20px;cursor:pointer;list-style:none;padding:18px 20px}}.history-card summary::-webkit-details-marker{{display:none}}.summary-copy strong,.summary-copy span{{display:block}}.summary-copy strong{{font-size:18px;font-weight:600}}.summary-copy span{{margin-top:3px;color:var(--muted);font-size:13px}}.summary-action{{flex:none;color:var(--green);font-size:13px;font-weight:850}}.history-card[open] .summary-action{{font-size:0}}.history-card[open] .summary-action::after{{content:"\ub2eb\uae30";font-size:13px}}.history-body{{padding:0 20px 20px}}.history-card[open]{{box-shadow:var(--shadow)}}
    .footer{{display:flex;justify-content:space-between;gap:20px;margin-top:28px;padding:18px 2px 0;border-top:1px solid var(--line);color:var(--muted);font-size:12px}}.footer strong{{color:var(--green)}}
    @media (max-width:980px){{.hero,.content-grid{{grid-template-columns:1fr}}.hero-status{{min-height:auto}}.secondary-metrics{{grid-template-columns:repeat(2,1fr)}}.secondary-metrics .metric:nth-child(2){{border-right:0}}}}
    @media (max-width:767px){{.shell{{padding:12px 14px 36px}}.topbar{{display:grid;grid-template-columns:1fr;gap:12px;align-items:start}}.brand-copy small{{display:none}}.mode-status{{max-width:none;flex-wrap:wrap}}.topnav{{gap:2px;justify-content:flex-start}}.nav-link{{padding:8px 9px;font-size:13px}}.hero{{padding:34px 0 18px;gap:16px}}.hero h1{{font-size:30px}}.primary-metrics{{grid-template-columns:1fr}}.primary-metrics .metric{{border-right:0;border-bottom:1px solid var(--line)}}.primary-metrics .metric:last-child{{border-bottom:0}}.content-grid{{gap:14px}}.panel{{padding:19px 16px}}.secondary-metrics{{grid-template-columns:1fr}}.secondary-metrics .metric{{border-right:0;border-bottom:1px solid var(--line)}}.secondary-metrics .metric:last-child{{border-bottom:0}}.history-heading{{display:block}}.history-heading p{{margin-top:6px;text-align:left}}.history-card summary{{padding:16px}}.summary-copy span{{display:none}}.history-body{{padding:0 12px 14px}}.footer{{display:block}}.footer span{{display:block;margin-top:5px}}}}
    @media (prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}*,*::before,*::after{{animation-duration:.01ms!important;transition-duration:.01ms!important}}}}
    """

    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>K Group \uba85\ud568 \uc790\ub3d9\ubc1c\uc8fc \uc2dc\uc2a4\ud15c</title>
  <style>{styles}</style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <a class="brand" href="/dashboard" aria-label="\uba85\ud568 \ubc1c\uc8fc \ub300\uc2dc\ubcf4\ub4dc \uc0c8\ub85c\uace0\uce68">
        <span class="brand-mark" aria-hidden="true">B</span>
        <span class="brand-copy">\uba85\ud568 \ubc1c\uc8fc<small>OPERATIONS DESK</small></span>
      </a>
      <div class="mode-status" data-send-mode="{mode}">{_badge(mode_label, mode_tone)}<span>{escape(mode_explanation)}</span></div>
      <nav class="topnav" aria-label="\uc8fc\uc694 \uba54\ub274">
        <a class="nav-link" href="/dashboard">\ud604\uc7ac \uc0c1\ud0dc</a>
        <a class="nav-link" href="/">\uc6b4\uc601 \ud3ec\ud138</a>
        <a class="nav-link nav-link--primary" href="/confirm-send">\ubc1c\uc1a1 \ub0b4\uc6a9 \uac80\ud1a0</a>
      </nav>
    </header>

    <main>
      <section class="hero" aria-labelledby="page-title">
        <div class="hero-copy">
          <span class="eyebrow">K GROUP / BUSINESS CARD AUTOMATION</span>
          <h1 id="page-title">K Group \uba85\ud568 \uc790\ub3d9\ubc1c\uc8fc \uc2dc\uc2a4\ud15c</h1>
          <p class="hero-description">\uba54\uc77c \uc218\uc9d1\ubd80\ud130 \uc2e0\uccad\uc11c \uac80\ud1a0, \uc5c5\uccb4 \ubc1c\uc1a1 \uacb0\uacfc\uae4c\uc9c0 \uc9c0\uae08 \ucc98\ub9ac\ud574\uc57c \ud560 \uc77c\uc744 \uc6b0\uc120\uc21c\uc704\ub85c \ubcf4\uc5ec\uc90d\ub2c8\ub2e4.</p>
        </div>
        <aside class="hero-status" data-tone="{tone}" aria-live="polite">
          <div><span class="status-label">LIVE STATUS</span><strong>{escape(status_title)}</strong><p>{escape(status_note)}</p></div>
          <div class="status-meta"><span>\ucd5c\uc885 \uac31\uc2e0</span><time>{_safe(payload.get("generated_at"))}</time></div>
        </aside>
      </section>

      <section class="primary-metrics" aria-label="\uc624\ub298\uc758 \ud575\uc2ec \uc9c0\ud45c">
        {_metric("\ubc1c\uc1a1 \uc900\ube44", ready_count, "\uc5c5\uccb4 \uc804\uc1a1 \uac00\ub2a5", "ready")}
        {_metric("\uac80\ud1a0 \ud544\uc694", review_count, "\ub204\ub77d \ubc0f \ud30c\uc2f1 \uc624\ub958", "warning" if review_count else "default")}
        {_metric("\ucd5c\uadfc \ubc1c\uc1a1 \uc131\uacf5", success_count, "\ucd5c\uadfc \ubc1c\uc8fc \ud68c\ucc28", "ready")}
      </section>

      <div class="content-grid">
        {_render_priority_section(payload, template)}
        <aside class="panel workflow-panel" aria-labelledby="workflow-title">
          <span class="section-kicker">AUTOMATION FLOW</span><h2 id="workflow-title">\uc791\uc5c5 \ud750\ub984</h2>
          <ol class="workflow-list">
            <li><strong>\uba54\uc77c \uc218\uc9d1</strong>\uc2e0\uccad \uba54\uc77c\uacfc \ucca8\ubd80\ud30c\uc77c\uc744 \ud655\uc778\ud569\ub2c8\ub2e4.</li>
            <li><strong>\uc2e0\uccad\uc11c \ubd84\uc11d</strong>\ud544\uc218 \ud56d\ubaa9\uacfc \uc911\ubcf5 \ubc1c\uc1a1 \uc774\ub825\uc744 \uac80\uc99d\ud569\ub2c8\ub2e4.</li>
            <li><strong>\ubc1c\uc8fc \ucd08\uc548 \uc900\ube44</strong>\uc5c5\uccb4 \uc218\uc2e0\uc778, \ubcf8\ubb38, \ucca8\ubd80\ud30c\uc77c\uc744 \uad6c\uc131\ud569\ub2c8\ub2e4.</li>
            {workflow_final_step}
          </ol>
        </aside>
      </div>

      <section class="secondary-metrics" aria-label="\uc6b4\uc601 \ubcf4\uc870 \uc9c0\ud45c">
        {_metric("\uc2e0\uccad \ud30c\uc77c", payload.get("request_file_count"), "\ud604\uc7ac \uc778\ubc15\uc2a4")}
        {_metric("\uc0dd\uc131\ub41c \ucd08\uc548", payload.get("draft_count"), "\uac80\ud1a0 \ub300\uc0c1")}
        {_metric("\ubc1c\uc1a1 \uc2e4\ud328", fail_count, "\ucd5c\uadfc \ubc1c\uc8fc \ud68c\ucc28", "error" if fail_count else "default")}
        {_metric("\uc911\ubcf5 \uc81c\uc678 \ub204\uc801", sent_total, "\uc7ac\ubc1c\uc1a1 \ubc29\uc9c0")}
      </section>

      {_render_collection_panel(fetch_result)}

      <section class="history-section" aria-labelledby="history-title">
        <div class="history-heading"><div><span class="section-kicker">AUDIT TRAIL</span><h2 id="history-title">\ucc98\ub9ac \uc774\ub825</h2></div><p>\ud544\uc694\ud55c \ud45c\ub9cc \uc5f4\uc5b4\ubcf4\uc138\uc694. \uac01 \ud45c\ub294 \ub3c5\ub9bd\uc801\uc73c\ub85c \uad00\ub9ac\ub429\ub2c8\ub2e4.</p></div>
        <div class="history-stack">
          {render_mail_history_table(import_history)}
          {render_send_history_table(send_history)}
          {render_latest_send_results_table((send_result.get("results") or [])[:20], open_by_default=fail_count > 0)}
        </div>
      </section>
    </main>

    <footer class="footer"><strong>\uba85\ud568 \ubc1c\uc8fc \uc6b4\uc601 \ub300\uc2dc\ubcf4\ub4dc</strong><span>\uba54\uc77c \uc218\uc9d1 {_safe(fetch_result.get("fetched_at"))} · \ucd5c\uadfc \ubc1c\uc1a1 {_safe(send_result.get("sent_at"))}</span></footer>
  </div>
</body>
</html>'''