import importlib.util
import re
import unittest

import business_card_dashboard as dashboard


def api(name):
    value = getattr(dashboard, name, None)
    if value is None:
        raise AssertionError(f"missing dashboard API: {name}")
    return value


def dashboard_fixture(*, ready_count=1, pending_count=0, send_result=None):
    payload = {
        "generated_at": "2026-07-27T12:00:00",
        "request_file_count": 4,
        "draft_count": ready_count + pending_count,
        "ready_count": ready_count,
        "pending_count": pending_count,
        "skipped_sent_files": ["already-sent.xlsx"],
        "parse_errors": [
            {"file": "<script>.xlsx", "error": "<b>broken</b>"},
        ],
        "rejected_files": [
            {"file": "leave&plan.xlsx", "reason": "not a request sheet"},
        ],
        "drafts": [
            {
                "source_file": "ready.xlsx",
                "request_date": "2026-07-27",
                "request_count": 3,
                "status": "ready",
                "vendor_to": "vendor@example.com",
                "missing_fields": [],
            }
        ],
    }
    if pending_count:
        payload["drafts"].append(
            {
                "source_file": "pending.xlsx",
                "request_date": "2026-07-27",
                "request_count": 1,
                "status": "pending",
                "vendor_to": "vendor@example.com",
                "missing_fields": ["mobile"],
            }
        )
    state = {
        "sent_hashes": {"one": {}},
        "import_history": [
            {
                "fetched_at": "2026-07-27T11:00:00",
                "mail_scan_count": 5,
                "imported_count": 2,
                "skipped_count": 3,
                "note": "scan",
            }
        ],
        "send_history": [
            {
                "sent_at": "2026-07-26T16:00:00",
                "success_count": 2,
                "fail_count": 0,
                "total_count": 2,
                "note": "batch",
            }
        ],
    }
    fetch_result = {
        "fetched_at": "2026-07-27T11:00:00",
        "mail_scan_count": 5,
        "imported_count": 2,
        "skipped_count": 3,
        "results": [],
    }
    result = (
        send_result
        if send_result is not None
        else {
            "sent_at": "2026-07-26T16:00:00",
            "success_count": 2,
            "fail_count": 0,
            "results": [],
        }
    )
    return payload, {"field_labels": {"mobile": "Mobile"}}, state, result, fetch_result



def dashboard_css_rules(html):
    style_match = re.search(r"<style>\s*(.*?)\s*</style>", html, re.DOTALL)
    if style_match is None:
        raise AssertionError("dashboard output is missing its style block")

    def parse_block(css, media=None):
        rules, cursor = [], 0
        while cursor < len(css):
            opening = css.find("{", cursor)
            if opening == -1:
                break
            selector = css[cursor:opening].strip()
            depth, closing = 1, opening + 1
            while closing < len(css) and depth:
                depth += (css[closing] == "{") - (css[closing] == "}")
                closing += 1
            if depth:
                raise AssertionError("dashboard CSS has an unclosed rule")
            body = css[opening + 1 : closing - 1]
            if selector.startswith("@media"):
                rules.extend(parse_block(body, selector))
            elif selector:
                declarations = {
                    name.strip(): value.strip()
                    for declaration in body.split(";")
                    if ":" in declaration
                    for name, value in [declaration.split(":", 1)]
                }
                rules.extend(((part.strip(), media), declarations) for part in selector.split(","))
            cursor = closing
        return rules

    merged = {}
    for rule, declarations in parse_block(style_match.group(1)):
        merged.setdefault(rule, {}).update(declarations)
    return merged


def assert_dashboard_typography_contract(test_case, html):
    rules = dashboard_css_rules(html)
    expected = {
        ("body", None): {"font-family": 'Pretendard,"Noto Sans KR","Malgun Gothic",system-ui,sans-serif', "font-size": "16px", "line-height": "1.6"},
        (".brand-copy small", None): {"font-size": "12px"},
        (".mode-status", None): {"font-size": "13px"},
        (".nav-link", None): {"font-size": "14px"},
        (".eyebrow", None): {"font-size": "12px"}, (".section-kicker", None): {"font-size": "12px"}, (".status-label", None): {"font-size": "12px"},
        (".hero h1", None): {"font-size": "30px"}, (".hero-description", None): {"font-size": "16px"}, (".hero-status p", None): {"font-size": "14px"},
        (".metric>span", None): {"font-size": "14px"}, (".metric small", None): {"font-size": "13px"}, (".metric strong", None): {"font-size": "38px"}, (".secondary-metrics .metric strong", None): {"font-size": "30px"},
        (".section-heading h2", None): {"font-size": "22px"}, (".section-description", None): {"font-size": "14px"}, (".work-title strong", None): {"font-size": "15px"}, (".work-copy p", None): {"font-size": "14px"}, (".badge", None): {"font-size": "12px"},
        (".workflow-list li", None): {"font-size": "14px"}, (".workflow-list strong", None): {"font-size": "15px"}, (".workflow-list li::before", None): {"font-size": "18px"},
        ("th", None): {"font-size": "12px"}, ("td", None): {"font-size": "13px"}, (".empty-state", None): {"font-size": "14px"},
        (".history-heading h2", None): {"font-size": "24px"}, (".history-heading p", None): {"font-size": "14px"}, (".summary-copy span", None): {"font-size": "13px"}, (".summary-action", None): {"font-size": "13px"}, (".history-card[open] .summary-action::after", None): {"font-size": "13px"}, (".footer", None): {"font-size": "12px"},
        (".nav-link", "@media (max-width:767px)"): {"font-size": "13px"}, (".hero h1", "@media (max-width:767px)"): {"font-size": "30px"},
    }
    for rule, properties in expected.items():
        test_case.assertIn(rule, rules, f"missing CSS rule {rule}")
        for name, value in properties.items():
            test_case.assertEqual(rules[rule].get(name), value, f"{rule[0]} {name}")
    font_family_rules = [rule for rule, properties in rules.items() if "font-family" in properties]
    test_case.assertEqual(font_family_rules, [("body", None)], "only body may declare font-family")
    font_shorthand_rules = [rule for rule, properties in rules.items() if "font" in properties]
    test_case.assertEqual(font_shorthand_rules, [], "font shorthand declarations are not permitted")
    inline_font_declarations = []
    for match in re.finditer(r"\bstyle=([\"'])(.*?)\1", html, re.DOTALL):
        for declaration in match.group(2).split(";"):
            if ":" in declaration:
                property_name = declaration.split(":", 1)[0].strip()
                if property_name in {"font-family", "font"}:
                    inline_font_declarations.append(property_name)
    test_case.assertEqual(inline_font_declarations, [], "inline font declarations are not permitted")
class DashboardDesignTests(unittest.TestCase):
    def test_dashboard_presentation_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec("business_card_dashboard"))

    def test_dashboard_uses_k_group_system_title(self):
        html = api("render_dashboard_html")(*dashboard_fixture())

        self.assertIn("<title>K Group \uba85\ud568 \uc790\ub3d9\ubc1c\uc8fc \uc2dc\uc2a4\ud15c</title>", html)
        self.assertIn('<h1 id="page-title">K Group \uba85\ud568 \uc790\ub3d9\ubc1c\uc8fc \uc2dc\uc2a4\ud15c</h1>', html)
        self.assertNotIn("\uc624\ub298\uc758 \ubc1c\uc8fc\ub97c", html)

    def test_each_history_table_is_independent(self):
        mail_html = api("render_mail_history_table")(
            [{"fetched_at": "now", "mail_scan_count": 1, "imported_count": 1, "skipped_count": 0, "note": "ok"}]
        )
        send_html = api("render_send_history_table")(
            [{"sent_at": "now", "success_count": 1, "fail_count": 0, "total_count": 1, "note": "ok"}]
        )
        latest_html = api("render_latest_send_results_table")(
            [{"sent_at": "now", "subject": "Vendor order", "ok": True, "message": "sent"}]
        )

        self.assertIn("\uba54\uc77c \uc218\uc9d1 \uc774\ub825", mail_html)
        self.assertNotIn("\ubc1c\uc1a1 \uc774\ub825", mail_html)
        self.assertIn("\ubc1c\uc1a1 \uc774\ub825", send_html)
        self.assertNotIn("\uba54\uc77c \uc218\uc9d1 \uc774\ub825", send_html)
        self.assertIn("\ucd5c\uadfc \ubc1c\uc1a1 \uacb0\uacfc \uc0c1\uc138", latest_html)
        self.assertIn("Vendor order", latest_html)

    def test_dashboard_puts_priority_work_before_history(self):
        html = api("render_dashboard_html")(*dashboard_fixture())

        self.assertLess(html.index('data-section="priority"'), html.index('data-section="mail-history"'))
        self.assertLess(html.index('data-section="priority"'), html.index('data-section="send-history"'))

    def test_dashboard_only_exposes_safe_navigation(self):
        html = api("render_dashboard_html")(*dashboard_fixture())

        self.assertIn('href="/dashboard"', html)
        self.assertIn('href="/"', html)
        self.assertIn('href="/confirm-send"', html)
        self.assertNotIn('action="/send"', html)
        self.assertNotIn('href="/send"', html)

    def test_ready_work_drives_hero_status(self):
        html = api("render_dashboard_html")(*dashboard_fixture(ready_count=3))

        self.assertIn("\ubc1c\uc1a1\uc744 \uae30\ub2e4\ub9ac\ub294 \uc2e0\uccad\uc774 3\uac74 \uc788\uc2b5\ub2c8\ub2e4", html)
        self.assertIn('data-tone="ready"', html)

    def test_review_work_drives_warning_status(self):
        html = api("render_dashboard_html")(*dashboard_fixture(ready_count=0, pending_count=2))

        self.assertIn("\ud655\uc778\uc774 \ud544\uc694\ud55c \uc2e0\uccad\uc774 3\uac74 \uc788\uc2b5\ub2c8\ub2e4", html)
        self.assertIn('data-tone="warning"', html)

    def test_dynamic_text_is_escaped_and_rejected_files_are_hidden(self):
        html = api("render_dashboard_html")(*dashboard_fixture())

        self.assertIn("&lt;script&gt;.xlsx", html)
        self.assertIn("&lt;b&gt;broken&lt;/b&gt;", html)
        self.assertNotIn("<script>.xlsx", html)
        self.assertNotIn("leave&amp;plan.xlsx", html)
        self.assertNotIn("\uba85\ud568 \uc2e0\uccad\uc11c \uc544\ub2d8", html)

    def test_latest_results_open_only_when_failures_exist(self):
        clean_html = api("render_dashboard_html")(*dashboard_fixture(send_result={"fail_count": 0, "results": []}))
        failed_html = api("render_dashboard_html")(
            *dashboard_fixture(
                send_result={
                    "fail_count": 1,
                    "results": [{"sent_at": "now", "subject": "retry", "ok": False, "reason": "timeout"}],
                }
            )
        )

        self.assertIn('<details class="history-card" data-section="latest-send-results">', clean_html)
        self.assertIn('<details class="history-card" data-section="latest-send-results" open>', failed_html)

    def test_dashboard_includes_responsive_and_accessibility_rules(self):
        html = api("render_dashboard_html")(*dashboard_fixture())

        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', html)
        self.assertIn("@media (max-width:767px)", html)
        self.assertIn("prefers-reduced-motion", html)
        self.assertIn(":focus-visible", html)

    def test_dashboard_typography_matches_portal_and_keeps_readable_minimums(self):
        html = api("render_dashboard_html")(*dashboard_fixture())

        self.assertNotIn("Georgia", html)
        self.assertNotIn("Times New Roman", html)
        assert_dashboard_typography_contract(self, html)

        font_override_html = html.replace("</style>", "h1{font-family:Arial}</style>")
        with self.assertRaisesRegex(AssertionError, "only body may declare font-family"):
            assert_dashboard_typography_contract(self, font_override_html)

        shorthand_override_html = html.replace("</style>", "h1{font:normal 16px Arial}</style>")
        with self.assertRaisesRegex(AssertionError, "font shorthand declarations are not permitted"):
            assert_dashboard_typography_contract(self, shorthand_override_html)

        inline_family_override_html = html.replace(
            '<h1 id="page-title"', '<h1 style="font-family:Arial" id="page-title"', 1
        )
        with self.assertRaisesRegex(AssertionError, "inline font declarations are not permitted"):
            assert_dashboard_typography_contract(self, inline_family_override_html)

        inline_shorthand_override_html = html.replace(
            '<h1 id="page-title"', '<h1 style="font:normal 16px Arial" id="page-title"', 1
        )
        with self.assertRaisesRegex(AssertionError, "inline font declarations are not permitted"):
            assert_dashboard_typography_contract(self, inline_shorthand_override_html)

        size_regression_html = html.replace(
            ".summary-action{flex:none;color:var(--green);font-size:13px;",
            ".summary-action{flex:none;color:var(--green);font-size:12px;",
            1,
        )
        with self.assertRaisesRegex(AssertionError, r"\.summary-action font-size"):
            assert_dashboard_typography_contract(self, size_regression_html)
    def test_mobile_header_uses_two_rows_to_prevent_brand_wrapping(self):
        html = api("render_dashboard_html")(*dashboard_fixture())

        self.assertIn(".topbar{display:grid;grid-template-columns:1fr;", html)
        self.assertIn(".brand-copy{white-space:nowrap}", html)

    def test_dashboard_renders_automatic_send_mode_badge_and_explanation(self):
        html = api("render_dashboard_html")(*dashboard_fixture(), send_mode="automatic")

        self.assertIn("\uc790\ub3d9 \ubc1c\uc1a1 \uc911", html)
        self.assertIn("\uba85\ud568 \uc694\uccad\uc11c\ub294 \uac80\uc99d \ud6c4 \uc989\uc2dc \ubc1c\uc1a1\ud569\ub2c8\ub2e4.", html)
        self.assertIn("\uc790\ub3d9 \ubc1c\uc1a1", html)
        self.assertIn("\uac80\uc99d\uc744 \ud1b5\uacfc\ud55c \uc0c8 \uba85\ud568 \uc2e0\uccad\uc11c\ub97c \uc989\uc2dc \ubc1c\uc1a1\ud569\ub2c8\ub2e4.", html)
        self.assertNotIn("\uc0ac\ub78c\uc774 \ucd5c\uc885 \uac80\ud1a0", html)
        self.assertIn('class="badge badge--warning"', html)

    def test_dashboard_defaults_to_manual_mode_badge_and_explanation(self):
        html = api("render_dashboard_html")(*dashboard_fixture())

        self.assertIn("\uc9c1\uc811 \ud655\uc778 \uc911", html)
        self.assertIn("\ucd5c\uc885 \ud655\uc778 \ud6c4 \ubc1c\uc1a1\ud569\ub2c8\ub2e4.", html)
        self.assertIn('class="badge badge--success"', html)

if __name__ == "__main__":
    unittest.main()