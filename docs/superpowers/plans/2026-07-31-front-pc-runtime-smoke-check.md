# 앞자리 PC 운영 모듈 점검 전환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with checkpoints.

**Goal:** 앞자리 PC 설치가 개발용 `python-docx`와 Git 없이 운영 모듈 점검만으로 성공하도록 전환한다.

**Architecture:** 오프라인 설치 배치파일은 패키지 해시 검증과 로컬 wheel 설치를 그대로 유지하고, 설치 후 `openpyxl`, `dotenv`, `business_card_mailer`, `business_card_portal`을 import하는 무부작용 스모크 점검만 실행한다. 개발 PC의 전체 `unittest` 실행은 유지하며 앞자리 PC 설치 흐름에서는 제거한다.

**Tech Stack:** Windows CMD batch, Python 3.13, `unittest`, `openpyxl`, `python-dotenv`, PowerShell SHA-256 검증.

## Global Constraints

- Git과 `python-docx`는 앞자리 PC에 설치하지 않는다.
- 설치 검증 과정에서 메일 조회·발송과 포털 시작을 하지 않는다.
- 오프라인 wheel과 `--require-hashes` 잠금 파일을 변경하지 않는다.
- 설치 실패 시 외부 Python 명령의 종료 코드를 그대로 반환한다.
- 기존 해시 검증, 한글·공백 경로, 추가·누락·변조 자산 차단 동작을 유지한다.

---

### Task 1: 운영 스모크 점검 회귀 테스트 추가

**Files:**
- Modify: `tests/test_offline_setup.py` (OfflineSetupTests)

**Interfaces:**
- Consumes: `offline_setup/install_offline.bat`의 `OFFLINE_SETUP_PYTHON` 및 `OFFLINE_SETUP_NO_PAUSE` 테스트 훅.
- Produces: 설치 배치파일이 `unittest`를 실행하지 않고 운영 import 점검으로 성공한다는 블랙박스 회귀 테스트.

- [ ] **Step 1: Write the failing test**

`test_runtime_smoke_check_does_not_run_development_suite`를 추가한다. 임시 프로젝트를 복사하고 가짜 Python 배치파일이 실행 인자를 기록하게 한다. 인자에 `unittest`가 있으면 종료 코드 53, 그 외에는 0을 반환하게 한다. 설치 배치파일 결과가 0이고 완료 문구를 포함하며 기록된 인자에 `-c`, `business_card_mailer`, `business_card_portal`이 있고 `unittest`가 없어야 한다.

```python
def test_runtime_smoke_check_does_not_run_development_suite(self):
    with self._copied_project("runtime smoke") as project_dir:
        fake_bin = project_dir / "fake-bin"
        fake_bin.mkdir()
        fake_python = fake_bin / "fake-python.cmd"
        argument_log = project_dir / "python-arguments.txt"
        fake_python.write_text(
            "@echo off\r\n"
            "echo %*>>\"%FAKE_ARGUMENT_LOG%\"\r\n"
            "echo %* | findstr /I \"unittest\" >nul\r\n"
            "if not errorlevel 1 exit /b 53\r\n"
            "exit /b 0\r\n",
            encoding="ascii",
        )
        environment = os.environ.copy()
        environment["FAKE_ARGUMENT_LOG"] = str(argument_log)
        environment["OFFLINE_SETUP_PYTHON"] = str(fake_python)
        environment["OFFLINE_SETUP_NO_PAUSE"] = "1"

        result = self._run_batch(project_dir, environment=environment)
        arguments = argument_log.read_text(encoding="utf-8", errors="replace")

    self.assertEqual(0, result.returncode, result.stdout)
    self.assertIn("[OK] OFFLINE_INSTALL_COMPLETE", result.stdout)
    self.assertIn("-c", arguments)
    self.assertIn("business_card_mailer", arguments)
    self.assertIn("business_card_portal", arguments)
    self.assertNotIn("unittest", arguments.lower())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3.13 -B -m unittest tests.test_offline_setup.OfflineSetupTests.test_runtime_smoke_check_does_not_run_development_suite -v`

Expected: FAIL because the current installer invokes `-B -m unittest discover` and the fake Python returns exit code 53.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_offline_setup.py
git commit -m "test: require front PC runtime smoke check"
```

### Task 2: Install runtime smoke check instead of development suite

**Files:**
- Modify: `offline_setup/install_offline.bat` around the current `PROJECT_TESTS_FAILED` block.

**Interfaces:**
- Consumes: Python executable selected by `:find_python`, verified local packages, and project root.
- Produces: `RUNTIME_SMOKE_CHECK_FAILED` with preserved Python exit code, or the existing `OFFLINE_INSTALL_COMPLETE` marker.

- [ ] **Step 1: Write minimal implementation**

Replace the current project-wide test block with:

```bat
echo [INFO] Checking runtime modules...
pushd "%PROJECT_DIR%" >nul 2>&1
set "PUSHD_EXIT=!ERRORLEVEL!"
if not "!PUSHD_EXIT!"=="0" (
    echo [ERROR] PROJECT_DIRECTORY_NOT_ACCESSIBLE: exit !PUSHD_EXIT!
    call :failure !PUSHD_EXIT!
    exit /b !PUSHD_EXIT!
)
call "%PYTHON_EXE%" -c "import openpyxl, dotenv, business_card_mailer, business_card_portal"
set "SMOKE_EXIT=!ERRORLEVEL!"
popd
if not "!SMOKE_EXIT!"=="0" (
    echo [ERROR] RUNTIME_SMOKE_CHECK_FAILED: exit !SMOKE_EXIT!
    call :failure !SMOKE_EXIT!
    exit /b !SMOKE_EXIT!
)
```

- [ ] **Step 2: Run the focused test to verify it passes**

Run: `py -3.13 -B -m unittest tests.test_offline_setup.OfflineSetupTests.test_runtime_smoke_check_does_not_run_development_suite -v`

Expected: PASS and the batch output ends with `[OK] OFFLINE_INSTALL_COMPLETE`.

- [ ] **Step 3: Commit the implementation**

```bash
git add offline_setup/install_offline.bat
git commit -m "fix: use runtime smoke check for front PC setup"
```

### Task 3: Align front PC instructions

**Files:**
- Modify: `앞자리PC_설치_실행.txt` in the offline installation step.

**Interfaces:**
- Consumes: the new batch output marker and existing manual sync/portal commands.
- Produces: instructions that do not tell the operator to install or troubleshoot development-only dependencies.

- [ ] **Step 1: Update the user-facing wording**

Change the installation checklist item from `전체 프로젝트 테스트` to `운영 필수 모듈 동작 확인`, and state that `docx`/Git are not required for the front PC setup.

- [ ] **Step 2: Audit the guide**

Run a UTF-8 text check that requires `운영 필수 모듈 동작 확인`, `install_offline.bat`, and `[OK] OFFLINE_INSTALL_COMPLETE`, and rejects `python-docx`, `winget install`, and `pip install --upgrade`.

- [ ] **Step 3: Commit the guide**

```bash
git add "앞자리PC_설치_실행.txt"
git commit -m "docs: clarify front PC runtime validation"
```

### Task 4: Full verification and handoff

**Files:**
- Test: `tests/test_offline_setup.py` and the full `tests/` suite.
- Verify: `offline_setup/install_offline.bat`, `offline_setup/SHA256SUMS.txt`, `offline_setup/requirements-offline.txt`.

**Interfaces:**
- Consumes: all implementation and documentation changes from Tasks 1–3.
- Produces: verified front PC bundle and exact commands for rerunning it.

- [ ] **Step 1: Run focused offline setup tests**

Run: `$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; py -3.13 -B -m unittest tests.test_offline_setup -v`

Expected: all offline bundle tests pass, including runtime smoke behavior, hash tampering, exact inventory, and Korean/space paths.

- [ ] **Step 2: Run the complete regression suite**

Run: `$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; py -3.13 -B -m unittest discover -s tests -v`

Expected: zero failures and zero errors.

- [ ] **Step 3: Verify the committed bundle directly**

Run: `offline_setup\install_offline.bat verify`

Expected: exit code 0 and `[OK] OFFLINE_BUNDLE_VERIFIED`.

- [ ] **Step 4: Commit the verification result**

```bash
git status --short
git log -1 --oneline
```

Expected: only intended commits are present and no untracked implementation files remain.
