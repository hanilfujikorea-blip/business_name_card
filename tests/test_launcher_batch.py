import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BAT_PATH = ROOT / "run_business_card_mailer.bat"


class LauncherBatchTests(unittest.TestCase):
    def test_user_python_candidates_precede_generic_fallback(self) -> None:
        text = BAT_PATH.read_text(encoding="utf-8-sig")
        launcher = (
            'if exist "%LocalAppData%\\Programs\\Python\\Launcher\\py.exe" '
            'set "PYTHON_CMD=%LocalAppData%\\Programs\\Python\\Launcher\\py.exe"'
        )
        python313 = (
            'if not defined PYTHON_CMD if exist '
            '"%LocalAppData%\\Programs\\Python\\Python313\\python.exe" '
            'set "PYTHON_CMD=%LocalAppData%\\Programs\\Python\\Python313\\python.exe"'
        )
        fallback = 'if not defined PYTHON_CMD set "PYTHON_CMD=python"'

        self.assertIn(launcher, text)
        self.assertIn(python313, text)
        self.assertLess(text.index(launcher), text.index(python313))
        self.assertLess(text.index(python313), text.index(fallback))

    def test_failed_portal_exit_code_is_preserved_for_both_dispatch_paths(self) -> None:
        for arguments in ((), ("portal",)):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                batch = root / BAT_PATH.name
                batch.write_bytes(BAT_PATH.read_bytes())
                (root / "business_card_mailer.py").write_text("", encoding="utf-8")
                (root / "business_card_portal.py").write_text(
                    "raise SystemExit(7)\n",
                    encoding="utf-8",
                )
                command = "call run_business_card_mailer.bat" + (
                    " " + " ".join(arguments) if arguments else ""
                )

                completed = subprocess.run(
                    ["cmd.exe", "/d", "/c", command],
                    cwd=root,
                    input="\n",
                    text=True,
                    capture_output=True,
                    timeout=15,
                    env={**os.environ, "EXIT_CODE": "0"},
                )

                self.assertEqual(
                    7,
                    completed.returncode,
                    completed.stdout + completed.stderr,
                )

    def test_batch_starts_with_ascii_echo_command_without_utf8_bom(self) -> None:
        self.assertTrue(BAT_PATH.read_bytes().startswith(b"@echo off"))


if __name__ == "__main__":
    unittest.main()