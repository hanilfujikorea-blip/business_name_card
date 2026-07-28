import json
import shutil
import unittest
import uuid
from pathlib import Path

from business_card_mail_editor import (
    effective_payload,
    load_overrides,
    render_mail_editor,
    save_editor_action,
    save_default_recipients,
    split_template_copy,
    update_default_recipients,
    validate_editor_values,
    validate_recipient_values,
)


def editor_values(**changes):
    values = {
        "vendor_to": "vendor@example.com",
        "vendor_cc": "manager@example.com",
        "subject": "[명함 발주] 2명",
        "greeting_text": "안녕하세요.",
        "request_text": "제작 요청드립니다.",
        "closing_text": "감사합니다.",
    }
    values.update(changes)
    return values


def sample_template():
    return {
        "vendor_to": "vendor@example.com",
        "vendor_cc": "",
        "subject_template": "[명함 발주] {{request_count}}명",
        "intro_lines": ["안녕하세요.", "제작 요청드립니다."],
        "closing_lines": ["감사합니다."],
        "field_labels": {},
    }


def sample_payload():
    return {
        "drafts": [
            {
                "draft_id": "draft-1",
                "source_hash": "abc123",
                "status": "ready",
                "vendor_to": "vendor@example.com",
                "vendor_cc": "",
                "subject": "기존 제목",
                "request_date": "2026/07/27",
                "request_count": 1,
                "requests": [
                    {
                        "request": {
                            "employee_name": "홍길동",
                            "department": "경영지원",
                        }
                    }
                ],
                "attachment_paths": [],
            }
        ]
    }


class MailEditorDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path.cwd() / f".test-mail-editor-{uuid.uuid4().hex}"
        self.root.mkdir()
        self.override_path = self.root / "overrides.json"
        self.template_path = self.root / "template.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_split_template_copy_separates_sections(self) -> None:
        self.assertEqual(
            ("안녕하세요.", "제작 요청드립니다.", "감사합니다."),
            split_template_copy(sample_template()),
        )

    def test_validation_rejects_invalid_cc_address(self) -> None:
        errors = validate_editor_values(editor_values(vendor_cc="valid@example.com; invalid"))
        self.assertEqual("올바른 이메일 주소를 입력하세요.", errors["vendor_cc"])

    def test_validation_requires_recipient_and_subject(self) -> None:
        errors = validate_editor_values(editor_values(vendor_to="", subject="  "))
        self.assertEqual("수신자를 한 명 이상 입력하세요.", errors["vendor_to"])
        self.assertEqual("제목을 입력하세요.", errors["subject"])

    def test_default_recipient_validation_requires_vendor_to(self) -> None:
        errors = validate_recipient_values({"vendor_to": "", "vendor_cc": ""})

        self.assertEqual({"vendor_to": "받는 사람을 입력하세요."}, errors)

    def test_default_recipient_validation_rejects_invalid_to_and_cc(self) -> None:
        errors = validate_recipient_values(
            {
                "vendor_to": "valid@example.com; invalid",
                "vendor_cc": "also-invalid",
            }
        )

        self.assertEqual(
            {
                "vendor_to": "올바른 이메일 주소를 입력하세요.",
                "vendor_cc": "올바른 이메일 주소를 입력하세요.",
            },
            errors,
        )

    def test_default_recipient_validation_accepts_comma_and_semicolon_lists(self) -> None:
        errors = validate_recipient_values(
            {
                "vendor_to": "first@example.com, second@example.com",
                "vendor_cc": "manager@example.com; audit@example.com",
            }
        )

        self.assertEqual({}, errors)

    def test_default_recipient_update_preserves_template_copy_and_subject(self) -> None:
        template = sample_template()
        template["custom_setting"] = {"enabled": True}

        updated = update_default_recipients(
            template,
            "new@example.com",
            "manager@example.com",
        )

        self.assertEqual("new@example.com", updated["vendor_to"])
        self.assertEqual("manager@example.com", updated["vendor_cc"])
        self.assertEqual("[명함 발주] {{request_count}}명", updated["subject_template"])
        self.assertEqual(["안녕하세요.", "제작 요청드립니다."], updated["intro_lines"])
        self.assertEqual(["감사합니다."], updated["closing_lines"])
        self.assertEqual({"enabled": True}, updated["custom_setting"])
        self.assertEqual("vendor@example.com", template["vendor_to"])

    def test_default_recipient_save_uses_atomic_json_and_preserves_other_keys(self) -> None:
        template = sample_template()
        template["custom_setting"] = {"enabled": True}

        errors = save_default_recipients(
            self.template_path,
            template,
            {
                "vendor_to": "new@example.com",
                "vendor_cc": "manager@example.com",
            },
        )

        saved = json.loads(self.template_path.read_text(encoding="utf-8"))
        self.assertEqual({}, errors)
        self.assertEqual("new@example.com", saved["vendor_to"])
        self.assertEqual("manager@example.com", saved["vendor_cc"])
        self.assertEqual("[명함 발주] {{request_count}}명", saved["subject_template"])
        self.assertEqual(["안녕하세요.", "제작 요청드립니다."], saved["intro_lines"])
        self.assertEqual({"enabled": True}, saved["custom_setting"])

    def test_invalid_default_recipients_are_not_saved(self) -> None:
        original = sample_template()
        self.template_path.write_text(
            json.dumps(original, ensure_ascii=False),
            encoding="utf-8",
        )

        errors = save_default_recipients(
            self.template_path,
            original,
            {"vendor_to": "invalid", "vendor_cc": ""},
        )

        saved = json.loads(self.template_path.read_text(encoding="utf-8"))
        self.assertEqual(
            {"vendor_to": "올바른 이메일 주소를 입력하세요."},
            errors,
        )
        self.assertEqual(original, saved)
    def test_effective_payload_ignores_stale_override(self) -> None:
        overrides = {
            "drafts": {
                "draft-1": {
                    **editor_values(vendor_to="changed@example.com"),
                    "source_hash": "stale",
                }
            }
        }

        result = effective_payload(sample_payload(), sample_template(), overrides)

        self.assertEqual("vendor@example.com", result["drafts"][0]["vendor_to"])

    def test_effective_payload_applies_override_and_escapes_copy(self) -> None:
        overrides = {
            "drafts": {
                "draft-1": {
                    **editor_values(
                        vendor_to="changed@example.com",
                        request_text="<b>제작 요청</b>",
                    ),
                    "source_hash": "abc123",
                }
            }
        }

        draft = effective_payload(sample_payload(), sample_template(), overrides)["drafts"][0]

        self.assertEqual("changed@example.com", draft["vendor_to"])
        self.assertIn("&lt;b&gt;제작 요청&lt;/b&gt;", draft["html_body"])
        self.assertNotIn("<b>제작 요청</b>", draft["html_body"])

    def test_save_one_persists_subject_and_source_hash(self) -> None:
        errors = save_editor_action(
            scope="one",
            payload=sample_payload(),
            template=sample_template(),
            override_path=self.override_path,
            template_path=self.template_path,
            draft_id="draft-1",
            source_hash="abc123",
            values=editor_values(subject="개별 제목"),
        )

        saved = load_overrides(self.override_path)["drafts"]["draft-1"]
        self.assertEqual({}, errors)
        self.assertEqual("abc123", saved["source_hash"])
        self.assertEqual("개별 제목", saved["subject"])

    def test_save_all_preserves_each_subject(self) -> None:
        payload = sample_payload()
        payload["drafts"].append(
            {
                **payload["drafts"][0],
                "draft_id": "draft-2",
                "source_hash": "def456",
                "subject": "두 번째 제목",
            }
        )

        errors = save_editor_action(
            scope="all",
            payload=payload,
            template=sample_template(),
            override_path=self.override_path,
            template_path=self.template_path,
            draft_id="draft-1",
            source_hash="abc123",
            values=editor_values(subject="전체 복사 금지"),
        )

        saved = load_overrides(self.override_path)["drafts"]
        self.assertEqual({}, errors)
        self.assertNotIn("subject", saved["draft-1"])
        self.assertNotIn("subject", saved["draft-2"])
        self.assertEqual("vendor@example.com", saved["draft-2"]["vendor_to"])

    def test_save_defaults_updates_only_approved_template_keys(self) -> None:
        template = sample_template()
        self.template_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")

        errors = save_editor_action(
            scope="defaults",
            payload=sample_payload(),
            template=template,
            override_path=self.override_path,
            template_path=self.template_path,
            draft_id="draft-1",
            source_hash="abc123",
            values=editor_values(
                vendor_to="new@example.com",
                vendor_cc="copy@example.com",
                subject="기본 제목으로 저장되면 안 됨",
                request_text="새 기본 요청 문구",
            ),
        )

        saved = json.loads(self.template_path.read_text(encoding="utf-8"))
        self.assertEqual({}, errors)
        self.assertEqual("new@example.com", saved["vendor_to"])
        self.assertEqual("copy@example.com", saved["vendor_cc"])
        self.assertEqual(["안녕하세요.", "새 기본 요청 문구"], saved["intro_lines"])
        self.assertEqual("[명함 발주] {{request_count}}명", saved["subject_template"])
        self.assertFalse(self.override_path.exists())



    def test_mail_body_exposes_safe_preview_sections(self) -> None:
        overrides = {"drafts": {"draft-1": {**editor_values(), "source_hash": "abc123"}}}
        body = effective_payload(sample_payload(), sample_template(), overrides)["drafts"][0]["html_body"]
        self.assertIn("data-mail-section='intro'", body)
        self.assertIn("data-mail-section='order-details'", body)
        self.assertIn("data-mail-section='closing'", body)

    def test_editor_renders_three_panels_and_save_scopes(self) -> None:
        html = render_mail_editor(sample_payload(), sample_template(), {}, "secret")
        self.assertIn('class="mail-list"', html)
        self.assertIn('class="editor-panel"', html)
        self.assertIn('class="preview-panel"', html)
        self.assertIn('value="one"', html)
        self.assertIn('value="all"', html)
        self.assertIn('value="defaults"', html)
        self.assertIn('name="csrf_token" value="secret"', html)
        self.assertIn('name="draft_digest"', html)

    def test_editor_protects_generated_details_and_escapes_copy(self) -> None:
        overrides = {
            "drafts": {
                "draft-1": {
                    **editor_values(request_text="<script>alert(1)</script>"),
                    "source_hash": "abc123",
                }
            }
        }
        html = render_mail_editor(sample_payload(), sample_template(), overrides, "secret")
        self.assertIn('data-protected="order-details"', html)
        self.assertNotIn('name="requests"', html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_editor_shows_safe_empty_state(self) -> None:
        html = render_mail_editor({"drafts": []}, sample_template(), {}, "secret")
        self.assertIn("현재 발송 준비된 메일이 없습니다.", html)
        self.assertNotIn('class="final-send-button"', html)

    def test_editor_hides_final_send_while_validation_errors_are_visible(self) -> None:
        html = render_mail_editor(
            sample_payload(),
            sample_template(),
            {},
            "secret",
            errors={"vendor_cc": "올바른 이메일 주소를 입력하세요."},
            posted_values=editor_values(vendor_cc="invalid"),
        )
        self.assertIn("올바른 이메일 주소를 입력하세요.", html)
        self.assertNotIn('class="final-send-button"', html)

    def test_editor_preserves_javascript_newline_escapes(self) -> None:
        html = render_mail_editor(sample_payload(), sample_template(), {}, "secret")
        self.assertIn(r"split(/\r?\n/)", html)
        self.assertIn(r".value+'\n'+form", html)

    def test_editor_renders_automatic_send_mode_badge_and_explanation(self) -> None:
        html = render_mail_editor(
            sample_payload(), sample_template(), {}, "secret", send_mode="automatic"
        )

        self.assertIn("\uc790\ub3d9 \ubc1c\uc1a1 \uc911", html)
        self.assertIn("\uba85\ud568 \uc694\uccad\uc11c\ub294 \uac80\uc99d \ud6c4 \uc989\uc2dc \ubc1c\uc1a1\ud569\ub2c8\ub2e4.", html)
        self.assertIn('class="mode-badge mode-badge--warning"', html)

    def test_editor_defaults_to_manual_send_mode_badge_and_explanation(self) -> None:
        html = render_mail_editor(sample_payload(), sample_template(), {}, "secret")

        self.assertIn("\uc9c1\uc811 \ud655\uc778 \uc911", html)
        self.assertIn("\ucd5c\uc885 \ud655\uc778 \ud6c4 \ubc1c\uc1a1\ud569\ub2c8\ub2e4.", html)
        self.assertIn('class="mode-badge mode-badge--success"', html)

if __name__ == "__main__":
    unittest.main()
