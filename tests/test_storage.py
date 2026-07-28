import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from business_card_storage import (
    OperationLock,
    OperationLockedError,
    atomic_save_json,
    recover_json_file,
)


class StorageTests(unittest.TestCase):
    def test_recover_json_file_preserves_first_object_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "state.json"
            backup = root / "backups"
            source.write_text('{"sent_hashes":{"abc":{}},"send_history":[]}trailing', encoding="utf-8")

            backup_path = recover_json_file(
                source,
                backup,
                required_keys={"sent_hashes", "send_history"},
            )

            self.assertEqual({"abc": {}}, json.loads(source.read_text(encoding="utf-8"))["sent_hashes"])
            self.assertEqual(
                '{"sent_hashes":{"abc":{}},"send_history":[]}trailing',
                backup_path.read_text(encoding="utf-8"),
            )

    def test_atomic_save_json_replaces_with_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "state.json"
            atomic_save_json(path, {"value": "한글", "items": [1, 2, 3]})

            self.assertEqual(
                {"value": "한글", "items": [1, 2, 3]},
                json.loads(path.read_text(encoding="utf-8")),
            )
            self.assertEqual([], list(path.parent.glob("*.tmp")))

    def test_operation_lock_rejects_second_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mailer.lock"
            with OperationLock(path):
                with self.assertRaises(OperationLockedError):
                    with OperationLock(path):
                        self.fail("second owner must not acquire the lock")

    def test_operation_lock_reclaims_expired_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mailer.lock"
            path.write_text(json.dumps({"pid": 999999, "created_at": 1}), encoding="utf-8")
            old = time.time() - 120
            os.utime(path, (old, old))

            with OperationLock(path, stale_after_sec=60):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(os.getpid(), payload["pid"])

            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
