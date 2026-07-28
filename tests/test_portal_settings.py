import io
import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import business_card_portal as portal


def sample_template() -> dict:
    return {
        "vendor_to": "vendor@example.com",
        "vendor_cc": "manager@example.com",
        "subject_template": "[\uba85\ud568 \ubc1c\uc8fc] {{request_count}}\uba85",
        "intro_lines": ["\uc548\ub155\ud558\uc138\uc694.", "\uba85\ud568 \ubc1c\uc8fc \uc694\uccad\uc785\ub2c8\ub2e4."],
        "closing_lines": ["\uac10\uc0ac\ud569\ub2c8\ub2e4."],
        "field_labels": {},
    }


class HandlerHarness:
    def __init__(self, path: str, values: dict[str, str]) -> None:
        body = urlencode(values).encode("utf-8")
        self.handler = object.__new__(portal.PortalHandler)
        self.handler.path = path
        self.handler.headers = {"Content-Length": str(len(body))}
        self.handler.rfile = io.BytesIO(body)
        self.handler.wfile = io.BytesIO()
        self.statuses: list[int] = []
        self.headers: list[tuple[str, str]] = []
        self.handler.send_response = self.statuses.append
        self.handler.send_header = lambda name, value: self.headers.append((name, value))
        self.handler.end_headers = lambda: None

    def post(self) -> tuple[int, dict[str, str], str]:
        self.handler.do_POST()
        return self.statuses[-1], dict(self.headers), self.handler.wfile.getvalue().decode("utf-8")


class GetHandlerHarness:
    def __init__(self, path: str) -> None:
        self.handler = object.__new__(portal.PortalHandler)
        self.handler.path = path
        self.handler.wfile = io.BytesIO()
        self.statuses: list[int] = []
        self.headers: list[tuple[str, str]] = []
        self.handler.send_response = self.statuses.append
        self.handler.send_header = lambda name, value: self.headers.append((name, value))
        self.handler.end_headers = lambda: None

    def get(self) -> tuple[int, str]:
        self.handler.do_GET()
        return self.statuses[-1], self.handler.wfile.getvalue().decode("utf-8")


class PortalSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path.cwd() / f".test-portal-settings-{uuid.uuid4().hex}"
        root.mkdir()
        self.addCleanup(shutil.rmtree, root, True)
        self.settings_path = root / "automation_settings.json"
        self.template_path = root / "vendor_mail_template.json"
        self.template_path.write_text(json.dumps(sample_template(), ensure_ascii=False), encoding="utf-8")
        portal.PortalHandler.status_message = ""

    def portal_patches(self):
        return (
            patch.object(portal, "AUTOMATION_SETTINGS_PATH", self.settings_path),
            patch.object(portal.mailer, "TEMPLATE_PATH", self.template_path),
        )

    def test_portal_html_contains_manual_mode_controls_and_explanation(self) -> None:
        self.settings_path.write_text('{"send_mode":"manual"}', encoding="utf-8")
        settings_patch, template_patch = self.portal_patches()
        with settings_patch, template_patch:
            html = portal.portal_html()

        self.assertIn("\uc9c1\uc811 \uc2b9\uc778 \uc911", html)
        self.assertIn("\ucd5c\uc885 \ud655\uc778 \ud6c4 \ubc1c\uc1a1\ub429\ub2c8\ub2e4.", html)
        self.assertNotIn("\uc0c8 \uba85\ud568 \uc2e0\uccad\uc11c\ub294 \uac80\uc99d \ud6c4 \uc989\uc2dc \ubc1c\uc1a1\ub429\ub2c8\ub2e4.", html)
        self.assertIn('name="send_mode" value="manual"', html)
        self.assertIn('name="send_mode" value="automatic"', html)
        self.assertIn('aria-pressed="true"', html)
        self.assertGreaterEqual(html.count(f'name="csrf_token" value="{portal.CSRF_TOKEN}"'), 2)
        self.assertNotIn("linear-gradient", html)

    def test_portal_html_does_not_auto_refresh_editable_form(self) -> None:
        settings_patch, template_patch = self.portal_patches()
        with settings_patch, template_patch:
            html = portal.portal_html()
        self.assertNotIn('http-equiv="refresh"', html.lower())

    def test_portal_html_automatic_mode_explains_immediate_send_and_escapes_values(self) -> None:
        self.settings_path.write_text('{"send_mode":"automatic"}', encoding="utf-8")
        settings_patch, template_patch = self.portal_patches()
        with settings_patch, template_patch:
            html = portal.portal_html(
                errors={"vendor_to": "<\uc798\ubabb\ub41c \uc8fc\uc18c>"},
                posted_values={"vendor_to": 'bad@example.com"><script>alert(1)</script>', "vendor_cc": "copy@example.com"},
            )

        self.assertIn("\uc790\ub3d9 \ubc1c\uc1a1 \uc911", html)
        self.assertIn("\uc0c8 \uba85\ud568 \uc2e0\uccad\uc11c\ub294 \uac80\uc99d \ud6c4 \uc989\uc2dc \ubc1c\uc1a1\ub429\ub2c8\ub2e4.", html)
        self.assertNotIn("\ucd5c\uc885 \ud655\uc778 \ud6c4 \ubc1c\uc1a1\ub429\ub2c8\ub2e4.", html)
        self.assertIn('name="send_mode" value="automatic" aria-pressed="true"', html)
        self.assertIn("&lt;\uc798\ubabb\ub41c \uc8fc\uc18c&gt;", html)
        self.assertIn("bad@example.com&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_portal_get_pages_render_the_persisted_mode(self) -> None:
        self.settings_path.write_text('{"send_mode":"automatic"}', encoding="utf-8")
        settings_patch, template_patch = self.portal_patches()
        with settings_patch, template_patch, \
            patch.object(portal.mailer, "load_drafts_payload", return_value={"drafts": []}), \
            patch.object(portal.mailer, "load_state", return_value={}), \
            patch.object(portal.mailer, "load_send_result", return_value={}), \
            patch.object(portal.mailer, "load_fetch_result", return_value={}):
            confirm_status, confirm_html = GetHandlerHarness("/confirm-send").get()
            dashboard_status, dashboard_html = GetHandlerHarness("/dashboard").get()

        self.assertEqual(200, confirm_status)
        self.assertEqual(200, dashboard_status)
        self.assertIn("\uc790\ub3d9 \ubc1c\uc1a1 \uc911", confirm_html)
        self.assertIn("\uc790\ub3d9 \ubc1c\uc1a1 \uc911", dashboard_html)

    def test_mail_editor_validation_error_rerenders_the_persisted_mode(self) -> None:
        self.settings_path.write_text('{"send_mode":"automatic"}', encoding="utf-8")
        settings_patch, template_patch = self.portal_patches()
        with settings_patch, template_patch, \
            patch.object(portal.mailer, "load_drafts_payload", return_value={"drafts": []}), \
            patch.object(portal, "save_editor_action", return_value={"vendor_to": "invalid"}):
            status, _, body = HandlerHarness(
                "/action/save-mail-edits",
                {"csrf_token": portal.CSRF_TOKEN, "draft_id": "draft-1", "source_hash": "source", "save_scope": "one", "vendor_to": "invalid", "vendor_cc": "", "subject": "subject", "greeting_text": "greeting", "request_text": "request", "closing_text": "closing"},
            ).post()
        self.assertEqual(400, status)
        self.assertIn("\uc790\ub3d9 \ubc1c\uc1a1 \uc911", body)

    def test_settings_posts_require_csrf(self) -> None:
        settings_patch, template_patch = self.portal_patches()
        with settings_patch, template_patch:
            mode_status, _, _ = HandlerHarness("/action/set-send-mode", {"send_mode": "automatic"}).post()
            recipients_status, _, _ = HandlerHarness("/action/save-default-mail-settings", {"vendor_to": "other@example.com", "vendor_cc": ""}).post()
        self.assertEqual(403, mode_status)
        self.assertEqual(403, recipients_status)
        self.assertFalse(self.settings_path.exists())

    def test_valid_mode_change_is_saved_and_redirected(self) -> None:
        settings_patch, template_patch = self.portal_patches()
        with settings_patch, template_patch:
            status, headers, _ = HandlerHarness("/action/set-send-mode", {"csrf_token": portal.CSRF_TOKEN, "send_mode": "automatic"}).post()
        self.assertEqual(303, status)
        self.assertEqual("/", headers["Location"])
        self.assertEqual({"send_mode": "automatic"}, json.loads(self.settings_path.read_text(encoding="utf-8")))

    def test_invalid_mode_is_rejected_without_overwriting_settings(self) -> None:
        self.settings_path.write_text('{"send_mode":"manual"}', encoding="utf-8")
        settings_patch, template_patch = self.portal_patches()
        with settings_patch, template_patch:
            status, _, _ = HandlerHarness("/action/set-send-mode", {"csrf_token": portal.CSRF_TOKEN, "send_mode": "scheduled"}).post()
        self.assertEqual(400, status)
        self.assertEqual({"send_mode": "manual"}, json.loads(self.settings_path.read_text(encoding="utf-8")))

    def test_valid_default_recipients_are_saved_and_redirected(self) -> None:
        settings_patch, template_patch = self.portal_patches()
        with settings_patch, template_patch:
            status, headers, _ = HandlerHarness("/action/save-default-mail-settings", {"csrf_token": portal.CSRF_TOKEN, "vendor_to": "new@example.com, orders@example.com", "vendor_cc": "manager@example.com; audit@example.com"}).post()
        saved = json.loads(self.template_path.read_text(encoding="utf-8"))
        self.assertEqual(303, status)
        self.assertEqual("/", headers["Location"])
        self.assertEqual("new@example.com, orders@example.com", saved["vendor_to"])
        self.assertEqual("manager@example.com; audit@example.com", saved["vendor_cc"])
        self.assertEqual("[\uba85\ud568 \ubc1c\uc8fc] {{request_count}}\uba85", saved["subject_template"])

    def test_invalid_default_recipients_render_400_without_saving(self) -> None:
        original = sample_template()
        settings_patch, template_patch = self.portal_patches()
        with settings_patch, template_patch:
            status, _, body = HandlerHarness("/action/save-default-mail-settings", {"csrf_token": portal.CSRF_TOKEN, "vendor_to": "<invalid>", "vendor_cc": "copy@example.com"}).post()
        self.assertEqual(400, status)
        self.assertIn('value="&lt;invalid&gt;"', body)
        self.assertEqual(original, json.loads(self.template_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()