import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import business_card_portal as portal


class PortalRuntimeTests(unittest.TestCase):
    def test_run_mailer_uses_current_python_interpreter(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(command, **kwargs):
            captured["command"] = command
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch.object(portal.subprocess, "run", side_effect=fake_run):
            portal.run_mailer("--help")

        self.assertEqual(sys.executable, captured["command"][0])

    def test_send_once_passes_effective_payload_to_mailer(self) -> None:
        payload = {"drafts": [{"status": "ready", "vendor_to": "edited@example.com"}]}
        result = {"success_count": 1, "fail_count": 0}
        with patch.object(portal.mailer, "send_ready_drafts", return_value=result) as sender:
            ok, message = portal.send_once(payload)

        self.assertTrue(ok)
        self.assertEqual("발송 완료: 성공 1 / 실패 0", message)
        self.assertEqual(payload, sender.call_args.kwargs["payload"])

    def test_sync_once_summarizes_automatic_dispatch_result(self) -> None:
        settings_path = (
            Path.cwd() / ".test-tmp" / f"portal-automation-{uuid.uuid4().hex}.json"
        )
        self.addCleanup(settings_path.unlink, missing_ok=True)
        settings_path.write_text('{"send_mode":"automatic"}', encoding="utf-8")
        new_file = Path.cwd() / ".test-tmp" / "new.xlsx"
        sync_result = {
            "fetch": {
                "mail_scan_count": 4,
                "imported_count": 1,
                "results": [
                    {"status": "imported", "saved_files": [str(new_file)]},
                ],
            },
            "drafts": {
                "draft_count": 1,
                "ready_count": 1,
                "pending_count": 0,
                "drafts": [
                    {
                        "id": "new-ready",
                        "status": "ready",
                        "source_file": str(new_file),
                    },
                ],
            },
        }
        send_result = {"success_count": 1, "fail_count": 0}

        with (
            patch.object(portal, "AUTOMATION_SETTINGS_PATH", settings_path),
            patch.object(
                portal.mailer,
                "run_locked_automation_cycle",
                return_value={"sync": sync_result, "send": send_result},
            ) as cycle,
        ):
            ok, message = portal.sync_once()

        self.assertTrue(ok)
        self.assertEqual(
            "새로고침 완료: 메일 4건 확인, 새로 가져옴 1건, "
            "발송 가능 1건, 자동 발송 성공 1건 / 실패 0건",
            message,
        )
        cycle.assert_called_once_with(settings_path=settings_path)

    def test_sync_once_safely_summarizes_cycle_exceptions(self) -> None:
        with patch.object(portal.mailer, "run_locked_automation_cycle", side_effect=TimeoutError("timeout")):
            ok, message = portal.sync_once()

        self.assertFalse(ok)
        self.assertEqual("메일 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도하세요.", message)

    def test_sync_once_does_not_leak_result_formatting_exceptions(self) -> None:
        with patch.object(
            portal.mailer,
            "run_locked_automation_cycle",
            return_value={"sync": {}, "send": None},
        ):
            try:
                ok, message = portal.sync_once()
            except Exception as exc:
                self.fail(f"sync_once leaked an exception: {exc}")

        self.assertFalse(ok)
        self.assertEqual("'fetch'", message)

if __name__ == "__main__":
    unittest.main()