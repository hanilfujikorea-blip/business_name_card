import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import business_card_mailer as mailer


class TextIntegrityTests(unittest.TestCase):
    def test_cli_help_uses_readable_korean_descriptions(self) -> None:
        help_text = mailer.build_parser().format_help()
        self.assertNotIn("??", help_text)
        self.assertIn("메일함", help_text)
        self.assertIn("발송", help_text)
        self.assertIn("대시보드", help_text)

    def test_missing_template_uses_readable_korean_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-template.json"
            with patch.object(mailer, "TEMPLATE_PATH", missing):
                template = mailer.load_template()

        self.assertEqual("[명함 발주] {{request_date}} / {{request_count}}명", template["subject_template"])
        self.assertEqual("안녕하세요.", template["intro_lines"][0])
        self.assertEqual("신청 인원", template["field_labels"]["request_count"])


if __name__ == "__main__":
    unittest.main()
