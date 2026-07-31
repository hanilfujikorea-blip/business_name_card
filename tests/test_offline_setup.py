import hashlib
import os
from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SETUP_DIR = ROOT / "offline_setup"
INSTALLER_NAME = "python-3.13.14-amd64.exe"
INSTALLER_SHA256 = "c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0"
SUCCESS_MARKER = "[OK] OFFLINE_BUNDLE_VERIFIED"
HASH_ERROR_MARKER = "[ERROR] HASH_MISMATCH"
MANIFEST_ERROR_MARKER = "[ERROR] MANIFEST_MISMATCH"
ASSET_INVENTORY_ERROR_MARKER = "[ERROR] UNEXPECTED_ASSET"
TEST_TMP_ROOT = Path(tempfile.gettempdir()) / "business-card-mailer-tests"
TEST_TMP_ROOT.mkdir(exist_ok=True)

EXPECTED_ASSET_HASHES = {
    INSTALLER_NAME: INSTALLER_SHA256,
    "requirements-offline.txt": "4290d838761485bb4dcccfbf1856186bc73d1f3ae35171221aee4baf0f25dd83",
    "wheels/et_xmlfile-2.0.0-py3-none-any.whl": "7a91720bc756843502c3b7504c77b8fe44217c85c537d85037f0f536151b2caa",
    "wheels/openpyxl-3.1.5-py2.py3-none-any.whl": "5282c12b107bffeef825f4617dc029afaf41d0ea60823bbb665ef3079dc79de2",
    "wheels/python_dotenv-1.2.2-py3-none-any.whl": "1d8214789a24de455a8b8bd8ae6fe3c6b69a5e3d64aa8a8e5d68e694bbcb285a",
}

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        digest, separator, relative_path = line.partition(" *")
        if separator != " *" or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise AssertionError(f"invalid SHA256SUMS line {line_number}: {raw_line!r}")
        normalized_path = relative_path.replace("\\", "/")
        if normalized_path in entries:
            raise AssertionError(f"duplicate SHA256SUMS path: {normalized_path}")
        entries[normalized_path] = digest
    return entries


class OfflineSetupTests(unittest.TestCase):
    def test_offline_assets_match_fixed_trusted_hashes(self):
        installer = SETUP_DIR / INSTALLER_NAME
        manifest_path = SETUP_DIR / "SHA256SUMS.txt"

        self.assertEqual(INSTALLER_SHA256, file_sha256(installer))
        self.assertEqual(EXPECTED_ASSET_HASHES, parse_manifest(manifest_path))
        for relative_path, expected_hash in EXPECTED_ASSET_HASHES.items():
            self.assertEqual(expected_hash, file_sha256(SETUP_DIR / relative_path))
    def test_git_checkout_keeps_trusted_text_assets_lf(self):
        paths = [
            "offline_setup/SHA256SUMS.txt",
            "offline_setup/requirements-offline.txt",
        ]
        result = subprocess.run(
            ["git", "-C", str(ROOT), "check-attr", "eol", "--", *paths],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual(
            [f"{path}: eol: lf" for path in paths],
            result.stdout.splitlines(),
        )
    def test_verify_mode_succeeds_from_korean_space_path(self):
        prefix = "\uba85\ud568 \uc624\ud504\ub77c\uc778 "
        project_name = "\uba85\ud568 \uc790\ub3d9\ubc1c\uc8fc \uc2dc\uc2a4\ud15c"
        with tempfile.TemporaryDirectory(prefix=prefix, dir=TEST_TMP_ROOT) as temp_dir:
            project_dir = Path(temp_dir) / project_name
            project_dir.mkdir()
            shutil.copytree(SETUP_DIR, project_dir / "offline_setup")
            shutil.copy2(ROOT / "requirements.txt", project_dir / "requirements.txt")

            result = self._run_verify(project_dir)

        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn(SUCCESS_MARKER, result.stdout)

    def test_verify_mode_rejects_tampered_wheel(self):
        prefix = "\uba85\ud568 \ubcc0\uc870\uac80\uc0ac "
        project_name = "\uba85\ud568 \uc790\ub3d9\ubc1c\uc8fc \uc2dc\uc2a4\ud15c"
        with tempfile.TemporaryDirectory(prefix=prefix, dir=TEST_TMP_ROOT) as temp_dir:
            project_dir = Path(temp_dir) / project_name
            project_dir.mkdir()
            shutil.copytree(SETUP_DIR, project_dir / "offline_setup")
            shutil.copy2(ROOT / "requirements.txt", project_dir / "requirements.txt")
            wheel = next((project_dir / "offline_setup" / "wheels").glob("*.whl"))
            with wheel.open("ab") as handle:
                handle.write(b"tampered")

            result = self._run_verify(project_dir)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn(HASH_ERROR_MARKER, result.stdout)

    def test_verify_mode_rejects_empty_manifest(self):
        with self._copied_project("empty manifest") as project_dir:
            (project_dir / "offline_setup" / "SHA256SUMS.txt").write_text("", encoding="ascii")
            result = self._run_verify(project_dir)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn(MANIFEST_ERROR_MARKER, result.stdout)

    def test_verify_mode_rejects_truncated_manifest(self):
        with self._copied_project("truncated manifest") as project_dir:
            manifest = project_dir / "offline_setup" / "SHA256SUMS.txt"
            lines = manifest.read_text(encoding="utf-8-sig").splitlines()
            manifest.write_text("\n".join(lines[:-1]) + "\n", encoding="ascii")
            result = self._run_verify(project_dir)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn(MANIFEST_ERROR_MARKER, result.stdout)

    def test_verify_mode_rejects_coordinated_wheel_and_manifest_change(self):
        with self._copied_project("coordinated change") as project_dir:
            setup_dir = project_dir / "offline_setup"
            wheel = next((setup_dir / "wheels").glob("*.whl"))
            wheel.write_bytes(wheel.read_bytes() + b"tampered")
            manifest = setup_dir / "SHA256SUMS.txt"
            lines = manifest.read_text(encoding="utf-8-sig").splitlines()
            wheel_fragment = f"wheels\\{wheel.name}"
            changed = [
                f"{file_sha256(wheel)} *{wheel_fragment}" if line.endswith(wheel_fragment) else line
                for line in lines
            ]
            manifest.write_text("\n".join(changed) + "\n", encoding="ascii")
            result = self._run_verify(project_dir)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn(MANIFEST_ERROR_MARKER, result.stdout)

    def test_verify_mode_rejects_extra_wheel(self):
        with self._copied_project("extra wheel") as project_dir:
            extra = project_dir / "offline_setup" / "wheels" / "openpyxl-9.9.9-py3-none-any.whl"
            extra.write_bytes(b"untrusted")
            result = self._run_verify(project_dir)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn(ASSET_INVENTORY_ERROR_MARKER, result.stdout)

    def test_verify_mode_rejects_missing_wheel(self):
        with self._copied_project("missing wheel") as project_dir:
            wheel = next((project_dir / "offline_setup" / "wheels").glob("*.whl"))
            wheel.unlink()
            result = self._run_verify(project_dir)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("[ERROR] MISSING_ASSET", result.stdout)

    def test_package_install_preserves_exit_code_and_uses_verified_lock(self):
        with self._copied_project("pip exit") as project_dir:
            (project_dir / "requirements.txt").write_text(
                "example @ https://invalid.example/package.whl\n", encoding="ascii"
            )
            fake_bin = project_dir / "fake-bin"
            fake_bin.mkdir()
            fake_python = fake_bin / "fake-python.cmd"
            argument_log = project_dir / "python-arguments.txt"
            fake_python.write_text(
                "@echo off\r\n"
                "echo %*>>\"%FAKE_ARGUMENT_LOG%\"\r\n"
                "exit /b 37\r\n",
                encoding="ascii",
            )
            (fake_bin / "py.cmd").write_text(
                f"@echo off\r\necho {fake_python}\r\nexit /b 0\r\n",
                encoding="ascii",
            )
            local_app_data = project_dir / "empty-local-app-data"
            local_app_data.mkdir()
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"
            environment["LocalAppData"] = str(local_app_data)
            environment["FAKE_ARGUMENT_LOG"] = str(argument_log)
            environment["OFFLINE_SETUP_PYTHON"] = str(fake_python)
            environment["OFFLINE_SETUP_NO_PAUSE"] = "1"

            result = self._run_batch(project_dir, environment=environment)
            self.assertTrue(argument_log.exists(), result.stdout)
            arguments = argument_log.read_text(encoding="utf-8", errors="replace")

        self.assertEqual(37, result.returncode, result.stdout)
        self.assertIn("requirements-offline.txt", arguments)
        self.assertNotIn("\\requirements.txt", arguments)
        self.assertIn("--no-index", arguments)
        self.assertIn("--require-hashes", arguments)
        self.assertIn("--isolated", arguments)
        self.assertIn("--no-cache-dir", arguments)

    @staticmethod
    @contextmanager
    def _copied_project(label: str):
        prefix = f"offline {label} "
        with tempfile.TemporaryDirectory(prefix=prefix, dir=TEST_TMP_ROOT) as temp_dir:
            project_dir = Path(temp_dir) / "project"
            project_dir.mkdir()
            shutil.copytree(SETUP_DIR, project_dir / "offline_setup")
            shutil.copy2(ROOT / "requirements.txt", project_dir / "requirements.txt")
            yield project_dir

    @staticmethod
    def _run_verify(project_dir: Path) -> subprocess.CompletedProcess[str]:
        return OfflineSetupTests._run_batch(project_dir, "verify")

    @staticmethod
    def _run_batch(
        project_dir: Path,
        *arguments: str,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        batch_path = project_dir / "offline_setup" / "install_offline.bat"
        return subprocess.run(
            [os.environ.get("ComSpec", "cmd.exe"), "/d", "/c", str(batch_path), *arguments],
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
            input="\n",
            env=environment,
        )

if __name__ == "__main__":
    unittest.main()
