import os
import unittest
from pathlib import Path
from unittest.mock import patch

import business_card_mailer as mailer


ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "inbox" / "requests"


class RequestClassificationTests(unittest.TestCase):
    def test_keyword_only_in_attachment_filename_is_rejected(self) -> None:
        accepted, reason = mailer.classify_business_card_attachment(
            {"subject": "신규 입사자 요청", "sender": "employee@example.com"},
            {"fileName": "명함신청서.xlsx", "fileExt": "xlsx"},
            {"keywords": ["명함"], "allowed_senders": []},
        )
        self.assertFalse(accepted)
        self.assertEqual("keyword_not_matched", reason)

    def test_keyword_in_subject_is_accepted(self) -> None:
        accepted, reason = mailer.classify_business_card_attachment(
            {"subject": "신규 입사자 명함 제작 요청", "sender": "employee@example.com"},
            {"fileName": "request.xlsx", "fileExt": "xlsx"},
            {"keywords": ["명함"], "allowed_senders": []},
        )
        self.assertTrue(accepted)
        self.assertEqual("accepted", reason)

    def test_mailbox_config_defaults_to_business_card_keyword(self) -> None:
        with patch.dict(os.environ):
            os.environ.pop("BUSINESS_CARD_MAILBOX_KEYWORDS", None)
            self.assertEqual(["명함"], mailer.business_card_mailbox_config()["keywords"])

    def test_excel_without_keyword_is_rejected(self) -> None:
        accepted, reason = mailer.classify_business_card_attachment(
            {"subject": "2026년 연차 계획", "sender": "employee@example.com"},
            {"fileName": "연차계획.xlsx", "fileExt": "xlsx"},
            {"keywords": ["명함", "business card"], "allowed_senders": []},
        )
        self.assertFalse(accepted)
        self.assertEqual("keyword_not_matched", reason)

    def test_unlisted_sender_is_rejected_when_allowlist_exists(self) -> None:
        accepted, reason = mailer.classify_business_card_attachment(
            {"subject": "명함 신청", "sender": "outsider@example.com"},
            {"fileName": "명함신청서.xlsx", "fileExt": "xlsx"},
            {"keywords": ["명함"], "allowed_senders": ["employee@example.com"]},
        )
        self.assertFalse(accepted)
        self.assertEqual("sender_not_allowed", reason)

    def test_legacy_xls_is_rejected_with_reason(self) -> None:
        accepted, reason = mailer.classify_business_card_attachment(
            {"subject": "명함 신청", "sender": "employee@example.com"},
            {"fileName": "명함신청서.xls", "fileExt": "xls"},
            {"keywords": ["명함"], "allowed_senders": []},
        )
        self.assertFalse(accepted)
        self.assertEqual("legacy_xls_not_supported", reason)

    def test_header_without_employee_name_is_rejected(self) -> None:
        accepted, reason = mailer.validate_header_match(
            {"department": 1, "title": 2, "email": 3, "mobile": 4},
            {"minimum_header_matches": 4, "required_header_fields": ["employee_name"]},
        )
        self.assertFalse(accepted)
        self.assertEqual("missing_header:employee_name", reason)

    def test_header_with_employee_name_and_four_matches_is_accepted(self) -> None:
        accepted, reason = mailer.validate_header_match(
            {"employee_name": 1, "department": 2, "email": 3, "mobile": 4},
            {"minimum_header_matches": 4, "required_header_fields": ["employee_name"]},
        )
        self.assertTrue(accepted)
        self.assertEqual("accepted", reason)

    def test_existing_leave_workbooks_are_not_extracted(self) -> None:
        mapping = mailer.load_mapping()
        names = ["2026 연차 사용계획 서식(7월_8월).xlsx", "2026 연차휴가 사용계획 서식(Form).xlsx"]
        for name in names:
            with self.subTest(name=name):
                self.assertEqual([], mailer.extract_requests_from_workbook(REQUESTS / name, mapping))

    def test_existing_business_card_workbook_is_still_extracted(self) -> None:
        mapping = mailer.load_mapping()
        rows = mailer.extract_requests_from_workbook(REQUESTS / "명함신청서(Form).xlsx", mapping)
        self.assertGreaterEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
