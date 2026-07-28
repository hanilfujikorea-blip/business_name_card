import json
import tempfile
import unittest
from pathlib import Path

from recover_business_card_state import recover_paths


class RecoveryCommandTests(unittest.TestCase):
    def test_recover_paths_keeps_state_history_counts_and_original_backups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fetch_path = root / "business_card_mail_fetch_result.json"
            state_path = root / "processed_state.json"
            backup_root = root / "backups"
            fetch_raw = json.dumps(
                {
                    "fetched_at": "2026-07-09T14:31:35",
                    "mail_scan_count": 5,
                    "imported_count": 0,
                    "skipped_count": 0,
                    "results": [],
                },
                ensure_ascii=False,
            ) + "}"
            state_payload = {
                "sent_hashes": {str(index): {} for index in range(5)},
                "send_history": [{"success_count": 2}],
                "fetched_message_uids": {},
                "import_history": [{"imported_count": 0}],
            }
            state_raw = json.dumps(state_payload, ensure_ascii=False) + "corrupt tail"
            fetch_path.write_text(fetch_raw, encoding="utf-8")
            state_path.write_text(state_raw, encoding="utf-8")

            result = recover_paths(fetch_path, state_path, backup_root)

            self.assertEqual(5, len(result["state"]["sent_hashes"]))
            self.assertEqual(1, len(result["state"]["send_history"]))
            self.assertEqual(5, json.loads(state_path.read_text(encoding="utf-8"))["sent_hashes"].__len__())
            self.assertEqual(5, json.loads(fetch_path.read_text(encoding="utf-8"))["mail_scan_count"])
            backup_dir = result["backup_dir"]
            self.assertEqual(fetch_raw, (backup_dir / fetch_path.name).read_text(encoding="utf-8"))
            self.assertEqual(state_raw, (backup_dir / state_path.name).read_text(encoding="utf-8"))

    def test_invalid_state_schema_does_not_modify_either_live_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fetch_path = root / "fetch.json"
            state_path = root / "state.json"
            fetch_raw = '{"fetched_at":"x","mail_scan_count":1,"imported_count":0,"skipped_count":0,"results":[]}tail'
            state_raw = '{"sent_hashes":{}}tail'
            fetch_path.write_text(fetch_raw, encoding="utf-8")
            state_path.write_text(state_raw, encoding="utf-8")

            with self.assertRaises(ValueError):
                recover_paths(fetch_path, state_path, root / "backups")

            self.assertEqual(fetch_raw, fetch_path.read_text(encoding="utf-8"))
            self.assertEqual(state_raw, state_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
