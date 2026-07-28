import hashlib
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import business_card_mailer as mailer
import business_card_sending as sending
from business_card_storage import OperationLock, OperationLockedError, atomic_save_json


class FakeClient:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    def guess_sender_account(self, preferred_address: str, preferred_personal: str):
        return preferred_address, preferred_personal, None

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeArchiveModule:
    def __init__(self, client: FakeClient) -> None:
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


class WaitingOperationLock:
    """Test-only adapter that waits while exercising the real filesystem lock."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.owner: OperationLock | None = None

    def __enter__(self):
        deadline = time.monotonic() + 3
        while True:
            owner = OperationLock(self.path)
            try:
                owner.acquire()
            except OperationLockedError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.005)
                continue
            self.owner = owner
            return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.owner is not None:
            self.owner.release()


class SafeSendingTests(unittest.TestCase):
    def _draft(self, source: Path, *, draft_id: str = "draft-1", recipient: str = "vendor@example.com") -> dict:
        source_hash = hashlib.sha1(source.read_bytes()).hexdigest()
        return {
            "draft_id": draft_id,
            "source_file": str(source),
            "source_hash": source_hash,
            "status": "ready",
            "subject": "명함 발주 테스트",
            "vendor_to": recipient,
            "vendor_cc": "",
            "html_body": "<p>test</p>",
            "attachment_paths": [str(source)],
        }

    def _run(
        self,
        root: Path,
        drafts: list[dict],
        client: FakeClient,
        injected_payload: dict | None = None,
    ):
        drafts_path = root / "drafts.json"
        state_path = root / "state.json"
        send_result_path = root / "send-result.json"
        lock_path = root / "operation.lock"
        atomic_save_json(drafts_path, {"drafts": drafts})
        atomic_save_json(
            state_path,
            {"sent_hashes": {}, "send_history": [], "fetched_message_uids": {}, "import_history": []},
        )
        module = FakeArchiveModule(client)
        with (
            patch.object(mailer, "DRAFTS_PATH", drafts_path),
            patch.object(mailer, "STATE_PATH", state_path),
            patch.object(mailer, "SEND_RESULT_PATH", send_result_path),
            patch.object(mailer, "OPERATION_LOCK_PATH", lock_path),
            patch.object(mailer, "build_drafts", return_value={"drafts": []}),
            patch.object(mailer, "write_dashboard", return_value=None),
        ):
            kwargs = {"archive_module": module}
            if injected_payload is not None:
                kwargs["payload"] = injected_payload
            result = mailer.send_ready_drafts(True, **kwargs)
        return result, mailer.load_json(state_path, {}), send_result_path

    def test_missing_attachment_never_calls_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "request.xlsx"
            source.write_bytes(b"request")
            draft = self._draft(source)
            draft["attachment_paths"] = [str(root / "missing.xlsx")]
            client = FakeClient([])

            result, _, _ = self._run(root, [draft], client)

            self.assertEqual(0, len(client.calls))
            self.assertEqual(1, result["fail_count"])
            self.assertIn("첨부파일", result["results"][0]["message"])

    def test_changed_source_hash_never_calls_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "request.xlsx"
            source.write_bytes(b"request")
            draft = self._draft(source)
            source.write_bytes(b"changed")
            client = FakeClient([])

            result, _, _ = self._run(root, [draft], client)

            self.assertEqual(0, len(client.calls))
            self.assertEqual(1, result["fail_count"])
            self.assertIn("변경", result["results"][0]["message"])

    def test_invalid_recipient_never_calls_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "request.xlsx"
            source.write_bytes(b"request")
            client = FakeClient([])

            result, _, _ = self._run(root, [self._draft(source, recipient="not-an-email")], client)

            self.assertEqual(0, len(client.calls))
            self.assertEqual(1, result["fail_count"])
            self.assertIn("수신자", result["results"][0]["message"])

    def test_invalid_cc_never_calls_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "request.xlsx"
            source.write_bytes(b"request")
            draft = self._draft(source)
            draft["vendor_cc"] = "not-an-email"
            client = FakeClient([{"ok": True, "status": 200, "code": "OK", "message": "sent"}])

            result, _, _ = self._run(root, [draft], client)

            self.assertEqual(0, len(client.calls))
            self.assertEqual(1, result["fail_count"])

    def test_send_ready_drafts_uses_injected_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "request.xlsx"
            source.write_bytes(b"request")
            draft = self._draft(source, recipient="edited@example.com")
            client = FakeClient([{"ok": True, "status": 200, "code": "OK", "message": "sent"}])

            result, _, _ = self._run(root, [draft], client, {"drafts": [draft]})

            self.assertEqual(1, result["success_count"])
            self.assertEqual("edited@example.com", client.calls[0]["to_txt"])

    def test_first_success_is_persisted_when_second_send_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.xlsx"
            second = root / "second.xlsx"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            client = FakeClient([
                {"ok": True, "status": 200, "code": "OK", "message": "sent"},
                RuntimeError("mail server failed"),
            ])
            first_draft = self._draft(first, draft_id="first")
            second_draft = self._draft(second, draft_id="second")

            result, state, _ = self._run(root, [first_draft, second_draft], client)

            self.assertEqual(2, len(client.calls))
            self.assertEqual(1, result["success_count"])
            self.assertEqual(1, result["fail_count"])
            self.assertIn(first_draft["source_hash"], state["sent_hashes"])
            self.assertNotIn(second_draft["source_hash"], state["sent_hashes"])

    def test_existing_operation_lock_blocks_send(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "request.xlsx"
            source.write_bytes(b"request")
            drafts_path = root / "drafts.json"
            state_path = root / "state.json"
            lock_path = root / "operation.lock"
            atomic_save_json(drafts_path, {"drafts": [self._draft(source)]})
            atomic_save_json(
                state_path,
                {"sent_hashes": {}, "send_history": [], "fetched_message_uids": {}, "import_history": []},
            )
            client = FakeClient([])
            with (
                OperationLock(lock_path),
                patch.object(mailer, "DRAFTS_PATH", drafts_path),
                patch.object(mailer, "STATE_PATH", state_path),
                patch.object(mailer, "OPERATION_LOCK_PATH", lock_path),
            ):
                with self.assertRaises(OperationLockedError):
                    mailer.send_ready_drafts(True, archive_module=FakeArchiveModule(client))
            self.assertEqual(0, len(client.calls))


    def test_contenders_reload_sent_state_after_the_send_lock_is_acquired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "request.xlsx"
            source.write_bytes(b"request")
            draft = self._draft(source)
            state_path = root / "state.json"
            send_result_path = root / "send-result.json"
            lock_path = root / "operation.lock"
            atomic_save_json(
                state_path,
                {"sent_hashes": {}, "send_history": [], "fetched_message_uids": {}, "import_history": []},
            )
            client = FakeClient([
                {"ok": True, "status": 200, "code": "OK", "message": "sent"},
                {"ok": True, "status": 200, "code": "OK", "message": "duplicate"},
            ])
            original_load_state = mailer.load_state
            initial_read_barrier = threading.Barrier(2)
            failures: list[BaseException] = []

            def synchronized_load_state() -> dict:
                snapshot = original_load_state()
                try:
                    initial_read_barrier.wait(timeout=0.25)
                except threading.BrokenBarrierError:
                    pass
                return snapshot

            def contender() -> None:
                try:
                    mailer.send_ready_drafts(
                        True,
                        archive_module=FakeArchiveModule(client),
                        payload={"drafts": [draft]},
                    )
                except BaseException as exc:
                    failures.append(exc)

            with (
                patch.object(mailer, "STATE_PATH", state_path),
                patch.object(mailer, "SEND_RESULT_PATH", send_result_path),
                patch.object(mailer, "OPERATION_LOCK_PATH", lock_path),
                patch.object(mailer, "load_state", side_effect=synchronized_load_state),
                patch.object(mailer, "build_drafts", return_value={"drafts": []}),
                patch.object(mailer, "write_dashboard", return_value=None),
                patch.object(sending, "OperationLock", WaitingOperationLock),
            ):
                threads = [threading.Thread(target=contender) for _ in range(2)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=5)

            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual([], failures)
            self.assertEqual(1, len(client.calls))


if __name__ == "__main__":
    unittest.main()
