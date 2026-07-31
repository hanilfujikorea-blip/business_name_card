import hashlib
import os
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
TEST_TMP_ROOT = ROOT / ".test-tmp"
TEST_TMP_ROOT.mkdir(exist_ok=True)


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
    def test_offline_assets_match_hash_manifest(self):
        installer = SETUP_DIR / INSTALLER_NAME
        manifest_path = SETUP_DIR / "SHA256SUMS.txt"
        wheel_dir = SETUP_DIR / "wheels"

        self.assertEqual(INSTALLER_SHA256, file_sha256(installer))
        manifests = parse_manifest(manifest_path)
        wheel_names = sorted(path.name for path in wheel_dir.glob("*.whl"))
        normalized_names = [name.lower().replace("-", "_") for name in wheel_names]
        for required_name in ("openpyxl_", "python_dotenv_", "et_xmlfile_"):
            self.assertTrue(
                any(name.startswith(required_name) for name in normalized_names),
                f"missing required wheel: {required_name}",
            )

        expected_paths = {INSTALLER_NAME, *(f"wheels/{name}" for name in wheel_names)}
        self.assertEqual(expected_paths, set(manifests))
        for relative_path, expected_hash in manifests.items():
            self.assertEqual(expected_hash, file_sha256(SETUP_DIR / relative_path))

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

    @staticmethod
    def _run_verify(project_dir: Path) -> subprocess.CompletedProcess[str]:
        batch_path = project_dir / "offline_setup" / "install_offline.bat"
        return subprocess.run(
            [os.environ.get("ComSpec", "cmd.exe"), "/d", "/c", str(batch_path), "verify"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
