import json
import tempfile
import unittest
from pathlib import Path

from business_card_automation import (
    load_automation_settings,
    save_send_mode,
    send_mode_label,
)


class AutomationSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "automation_settings.json"

    def test_missing_settings_fall_back_to_manual(self) -> None:
        self.assertEqual({"send_mode": "manual"}, load_automation_settings(self.path))

    def test_corrupt_or_invalid_settings_fall_back_to_manual(self) -> None:
        self.path.write_text("{", encoding="utf-8")
        self.assertEqual({"send_mode": "manual"}, load_automation_settings(self.path))

        self.path.write_text('{"send_mode":"unsupported"}', encoding="utf-8")
        self.assertEqual({"send_mode": "manual"}, load_automation_settings(self.path))

    def test_save_send_mode_persists_an_allowed_mode(self) -> None:
        self.assertEqual({"send_mode": "automatic"}, save_send_mode(self.path, "automatic"))
        self.assertEqual({"send_mode": "automatic"}, json.loads(self.path.read_text(encoding="utf-8")))

    def test_save_send_mode_rejects_an_unsupported_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "^지원하지 않는 발송 모드입니다\\.$"):
            save_send_mode(self.path, "scheduled")

    def test_send_mode_label_describes_both_allowed_modes(self) -> None:
        self.assertEqual("직접 승인 중", send_mode_label("manual"))
        self.assertEqual("자동 발송 중", send_mode_label("automatic"))


class UnhashableSendModeSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "automation_settings.json"

    def test_list_send_mode_falls_back_to_manual(self) -> None:
        self.path.write_text('{"send_mode":[]}', encoding="utf-8")

        self.assertEqual({"send_mode": "manual"}, load_automation_settings(self.path))

    def test_object_send_mode_falls_back_to_manual(self) -> None:
        self.path.write_text('{"send_mode":{}}', encoding="utf-8")

        self.assertEqual({"send_mode": "manual"}, load_automation_settings(self.path))


if __name__ == "__main__":
    unittest.main()
