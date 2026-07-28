import hashlib
import os
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import business_card_mailer as mailer
import business_card_portal as portal
from business_card_automation import run_automation_cycle, select_new_ready_payload
from business_card_storage import OperationLock, OperationLockedError, atomic_save_json


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def guess_sender_account(self, preferred_address: str, preferred_personal: str):
        return preferred_address, preferred_personal, None

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"ok": True, "status": 200, "code": "OK", "message": "sent"}


class RecordingArchiveModule:
    def __init__(self, client: RecordingClient) -> None:
        self.client = client
        self.config = SimpleNamespace(
            from_address="sender@example.com",
            from_personal="Sender",
            select_sign="0",
            priority="3",
        )

    def open_mailer_session(self, run_id: str):
        return {"client": self.client, "config": self.config}

    def close_mailer_session(self, session, run_id: str) -> None:
        return None


class AutomaticDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path.cwd() / ".test-tmp"
        self.settings_path = self.root / f"automation-{uuid.uuid4().hex}.json"
        self.addCleanup(self.settings_path.unlink, missing_ok=True)

    def sync_result(
        self,
        *,
        fetch_results: list[dict],
        drafts: list[dict],
    ) -> dict:
        return {
            "fetch": {
                "mail_scan_count": 7,
                "imported_count": sum(
                    1 for item in fetch_results if item["status"] == "imported"
                ),
                "results": fetch_results,
            },
            "drafts": {
                "generated_at": "2026-07-27T10:00:00",
                "request_file_count": len(drafts),
                "draft_count": len(drafts),
                "ready_count": sum(
                    1 for item in drafts if item["status"] == "ready"
                ),
                "pending_count": sum(
                    1 for item in drafts if item["status"] == "pending"
                ),
                "drafts": drafts,
            },
        }

    def enable_automatic_mode(self) -> None:
        self.settings_path.write_text(
            '{"send_mode":"automatic"}',
            encoding="utf-8",
        )

    def test_manual_mode_never_calls_send_callback(self) -> None:
        new_file = self.root / "new.xlsx"
        sync_result = self.sync_result(
            fetch_results=[
                {"status": "imported", "saved_files": [str(new_file)]},
            ],
            drafts=[
                {"id": "new", "status": "ready", "source_file": str(new_file)},
            ],
        )
        sent_payloads: list[dict] = []

        result = run_automation_cycle(
            lambda: sync_result,
            lambda payload: sent_payloads.append(payload) or {"success_count": 1},
            self.settings_path,
        )

        self.assertEqual([], sent_payloads)
        self.assertEqual(
            {
                "sync": sync_result,
                "send_mode": "manual",
                "selected_count": 0,
                "send": None,
            },
            result,
        )

    def test_automatic_mode_sends_only_new_ready_draft_once(self) -> None:
        self.enable_automatic_mode()
        new_file = self.root / "new.xlsx"
        old_file = self.root / "old.xlsx"
        pending_file = self.root / "pending.xlsx"
        new_draft = {
            "id": "new-ready",
            "status": "ready",
            "source_file": str(new_file),
            "vendor_to": "orders@example.com",
        }
        sync_result = self.sync_result(
            fetch_results=[
                {
                    "status": "imported",
                    "saved_files": [str(new_file), str(pending_file)],
                },
                {"status": "skipped", "saved_files": [str(old_file)]},
            ],
            drafts=[
                new_draft,
                {"id": "old-ready", "status": "ready", "source_file": str(old_file)},
                {
                    "id": "new-pending",
                    "status": "pending",
                    "source_file": str(pending_file),
                },
            ],
        )
        sent_payloads: list[dict] = []

        result = run_automation_cycle(
            lambda: sync_result,
            lambda payload: sent_payloads.append(payload)
            or {"success_count": 1, "fail_count": 0},
            self.settings_path,
        )

        self.assertEqual(1, len(sent_payloads))
        self.assertEqual(
            {
                "generated_at": "2026-07-27T10:00:00",
                "request_file_count": 3,
                "draft_count": 1,
                "ready_count": 1,
                "pending_count": 0,
                "drafts": [new_draft],
            },
            sent_payloads[0],
        )
        self.assertEqual("automatic", result["send_mode"])
        self.assertEqual(1, result["selected_count"])
        self.assertEqual(
            {"success_count": 1, "fail_count": 0},
            result["send"],
        )

    def test_automatic_mode_does_not_send_when_nothing_was_imported(self) -> None:
        self.enable_automatic_mode()
        old_file = self.root / "old.xlsx"
        sync_result = self.sync_result(
            fetch_results=[
                {"status": "skipped", "saved_files": [str(old_file)]},
            ],
            drafts=[
                {"id": "old-ready", "status": "ready", "source_file": str(old_file)},
            ],
        )
        sent_payloads: list[dict] = []

        result = run_automation_cycle(
            lambda: sync_result,
            lambda payload: sent_payloads.append(payload) or {},
            self.settings_path,
        )

        self.assertEqual([], sent_payloads)
        self.assertEqual(0, result["selected_count"])
        self.assertIsNone(result["send"])

    @unittest.skipUnless(os.name == "nt", "Windows path comparison behavior")
    def test_selector_normalizes_windows_path_case(self) -> None:
        saved_file = self.root / "CUSTOMER CARD.XLSX"
        source_file = Path(str(saved_file).swapcase())
        draft = {
            "id": "case-insensitive",
            "status": "ready",
            "source_file": str(source_file),
        }
        sync_result = self.sync_result(
            fetch_results=[
                {"status": "imported", "saved_files": [str(saved_file)]},
            ],
            drafts=[draft],
        )

        selected = select_new_ready_payload(sync_result)

        self.assertEqual([draft], selected["drafts"])
        self.assertEqual(1, selected["draft_count"])
        self.assertEqual(1, selected["ready_count"])
        self.assertEqual(0, selected["pending_count"])


    def test_automatic_sync_keeps_import_and_send_in_one_lock_scope(self) -> None:
        self.enable_automatic_mode()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "new.xlsx"
            source.write_bytes(b"request")
            source_hash = hashlib.sha1(source.read_bytes()).hexdigest()
            state_path = root / "state.json"
            send_result_path = root / "send-result.json"
            lock_path = root / "operation.lock"
            atomic_save_json(
                state_path,
                {"sent_hashes": {}, "send_history": [], "fetched_message_uids": {}, "import_history": []},
            )
            draft = {
                "draft_id": "new-ready",
                "status": "ready",
                "source_file": str(source),
                "source_hash": source_hash,
                "subject": "명함 발주 테스트",
                "vendor_to": "vendor@example.com",
                "vendor_cc": "",
                "html_body": "<p>test</p>",
                "attachment_paths": [str(source)],
            }
            imported = self.sync_result(
                fetch_results=[{"status": "imported", "saved_files": [str(source)]}],
                drafts=[draft],
            )
            skipped = self.sync_result(
                fetch_results=[{"status": "skipped", "saved_files": [str(source)]}],
                drafts=[draft],
            )
            cycle_count = 0
            contender_acquired = threading.Event()
            release_contender = threading.Event()
            contender_thread: threading.Thread | None = None

            def hold_next_lock() -> None:
                deadline = time.monotonic() + 3
                while True:
                    try:
                        with OperationLock(lock_path):
                            contender_acquired.set()
                            release_contender.wait(timeout=3)
                            return
                    except OperationLockedError:
                        if time.monotonic() >= deadline:
                            return
                        time.sleep(0.005)

            def fake_unlocked_sync(take: int = 0, include_sent: bool = False) -> dict:
                nonlocal cycle_count, contender_thread
                cycle_count += 1
                if cycle_count == 1:
                    contender_thread = threading.Thread(target=hold_next_lock)
                    contender_thread.start()
                    return imported
                return skipped

            original_run_sync_cycle = mailer.run_sync_cycle

            def expose_post_sync_lock_gap(take: int = 0, include_sent: bool = False) -> dict:
                result = original_run_sync_cycle(take=take, include_sent=include_sent)
                contender_acquired.wait(timeout=3)
                return result

            client = RecordingClient()
            module = RecordingArchiveModule(client)
            try:
                with (
                    patch.object(portal, "AUTOMATION_SETTINGS_PATH", self.settings_path),
                    patch.object(mailer, "AUTOMATION_SETTINGS_PATH", self.settings_path),
                    patch.object(mailer, "STATE_PATH", state_path),
                    patch.object(mailer, "SEND_RESULT_PATH", send_result_path),
                    patch.object(mailer, "OPERATION_LOCK_PATH", lock_path),
                    patch.object(mailer, "_unlocked_run_sync_cycle", side_effect=fake_unlocked_sync),
                    patch.object(mailer, "run_sync_cycle", side_effect=expose_post_sync_lock_gap),
                    patch.object(mailer, "load_archive_module", return_value=module),
                    patch.object(mailer, "build_drafts", return_value={"drafts": []}),
                    patch.object(mailer, "write_dashboard", return_value=None),
                ):
                    first_ok, _ = portal.sync_once()
                    release_contender.set()
                    if contender_thread is not None:
                        contender_thread.join(timeout=5)
                    second_ok, _ = portal.sync_once()
            finally:
                release_contender.set()
                if contender_thread is not None:
                    contender_thread.join(timeout=5)

            self.assertTrue(first_ok)
            self.assertTrue(second_ok)
            self.assertEqual(1, len(client.calls))


if __name__ == "__main__":
    unittest.main()