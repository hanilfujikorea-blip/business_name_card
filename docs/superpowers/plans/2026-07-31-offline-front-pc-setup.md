# Offline Front PC Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 인증서 오류가 있는 앞자리 PC에서도 인터넷 없이 Python 3.13.14, 프로젝트 의존성, 테스트를 한 번에 설치·검증할 수 있는 이동식 묶음을 만든다.

**Architecture:** `offline_setup` 폴더가 공식 Python 설치 파일, 로컬 wheelhouse, 해시 목록, 위치 독립적인 설치 배치파일을 소유한다. 기존 실행 안내는 온라인 설치와 개발 PC 고정 경로를 제거하고 오프라인 배치파일을 진입점으로 사용한다.

**Tech Stack:** Windows Batch, PowerShell SHA-256, Python 3.13.14, pip wheelhouse, unittest

## Global Constraints

- Python 설치 파일은 `python-3.13.14-amd64.exe`만 사용한다.
- 공식 Python 설치 파일 SHA-256은 `c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0`이다.
- 의존성은 `requirements.txt`의 `openpyxl>=3.1,<4`와 `python-dotenv>=1.0,<2` 및 모든 하위 의존성이다.
- 앞자리 PC에서는 패키지 인덱스에 연결하지 않고 `--no-index --find-links`만 사용한다.
- 인증서 검사를 비활성화하거나 `--trusted-host` 또는 HTTP를 사용하지 않는다.
- `.env`, 메일 주소, 토큰, 운영 상태 파일은 변경하지 않는다.
- 모든 배치파일은 공백과 한글이 포함된 임의의 프로젝트 경로에서 동작해야 한다.

---

### Task 1: 위치 독립적인 오프라인 설치 진입점과 안내

**Files:**
- Create: `tests/test_offline_setup.py`
- Create: `offline_setup/install_offline.bat`
- Modify: `앞자리PC_설치_실행.txt`

**Interfaces:**
- Consumes: `offline_setup/python-3.13.14-amd64.exe`, `offline_setup/wheels`, 루트 `requirements.txt`, 루트 `tests`
- Produces: 더블클릭 또는 CMD 실행이 가능한 `offline_setup/install_offline.bat`

- [ ] **Step 1: 배치파일과 안내서 요구사항을 검증하는 실패 테스트 작성**

Create `tests/test_offline_setup.py` with tests that assert:

```python
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SETUP_DIR = ROOT / "offline_setup"
INSTALLER_SHA256 = "c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0"


class OfflineSetupTests(unittest.TestCase):
    def test_install_script_is_offline_and_location_independent(self):
        text = (SETUP_DIR / "install_offline.bat").read_text(encoding="utf-8-sig")
        self.assertIn("%~dp0", text)
        self.assertIn("--no-index", text)
        self.assertIn("--find-links", text)
        self.assertIn(INSTALLER_SHA256, text.lower())
        self.assertNotIn("winget", text.lower())
        self.assertNotIn("--trusted-host", text.lower())
        self.assertNotIn("C:\\Users\\Felix", text)
        self.assertNotIn("C:\\WA", text)

    def test_guide_uses_offline_setup_without_development_pc_paths(self):
        text = (ROOT / "앞자리PC_설치_실행.txt").read_text(encoding="utf-8-sig")
        self.assertIn("offline_setup\\install_offline.bat", text)
        self.assertIn("프로젝트 상위 폴더\\3. SOA_fup_sales\\archive_mailer_api.py", text)
        self.assertNotIn("winget install", text.lower())
        self.assertNotIn("pip install --upgrade", text.lower())
        self.assertNotIn("C:\\Users\\Felix", text)
```

- [ ] **Step 2: 새 테스트가 예상대로 실패하는지 확인**

Run:

```cmd
py -3.13 -B -m unittest tests.test_offline_setup -v
```

Expected: FAIL because `offline_setup/install_offline.bat` does not exist and the guide still contains online and fixed-path instructions.

- [ ] **Step 3: 최소 오프라인 설치 배치파일 작성**

Create `offline_setup/install_offline.bat` that performs these exact stages:

```text
1. UTF-8 console and SCRIPT_DIR=%~dp0 initialization
2. PROJECT_DIR as the absolute parent directory of SCRIPT_DIR
3. PowerShell Get-FileHash verification against the official installer SHA-256
4. Existing Python 3.13 discovery through py launcher and %LocalAppData%\Programs\Python\Python313\python.exe
5. Per-user offline Python install when Python 3.13 is absent:
   /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1 InstallLauncherAllUsers=0
6. Offline dependency installation:
   python -m pip install --no-index --find-links="%SCRIPT_DIR%wheels" -r "%PROJECT_DIR%\requirements.txt"
7. Project test execution from PROJECT_DIR:
   python -B -m unittest discover -s tests -v
8. Nonzero exit and pause on every error; success message and pause on completion
```

The script must not start the portal or register scheduled tasks.

- [ ] **Step 4: 기존 TXT를 오프라인·위치 독립 절차로 수정**

Update `앞자리PC_설치_실행.txt` so that it:

```text
- tells the operator to copy the project and sibling `3. SOA_fup_sales` folder together;
- describes the mail module as `프로젝트 상위 폴더\3. SOA_fup_sales\archive_mailer_api.py`;
- runs `offline_setup\install_offline.bat` instead of winget and online pip;
- tells the operator to open CMD in the actual project folder rather than using a developer-PC path;
- registers the scheduled task with the current project directory expanded at execution time;
- preserves manual approval before automatic sending.
```

- [ ] **Step 5: 목표 테스트와 전체 테스트 실행**

Run:

```cmd
py -3.13 -B -m unittest tests.test_offline_setup -v
py -3.13 -B -m unittest discover -s tests -v
```

Expected: the new tests and all existing tests pass.

- [ ] **Step 6: 스크립트·안내서 변경 커밋**

```cmd
git add tests/test_offline_setup.py offline_setup/install_offline.bat "앞자리PC_설치_실행.txt"
git commit -m "Add offline front PC installer workflow"
```

---

### Task 2: 공식 설치 파일과 wheelhouse 묶음

**Files:**
- Modify: `tests/test_offline_setup.py`
- Create: `offline_setup/python-3.13.14-amd64.exe`
- Create: `offline_setup/wheels/*.whl`
- Create: `offline_setup/SHA256SUMS.txt`

**Interfaces:**
- Consumes: Python.org official installer URL and PyPI packages resolved from `requirements.txt`
- Produces: 인터넷이 없는 Windows x64/Python 3.13 환경에서 설치 가능한 검증된 로컬 자산

- [ ] **Step 1: 오프라인 자산 무결성 실패 테스트 추가**

Extend `tests/test_offline_setup.py` with tests that:

```text
- calculate SHA-256 of `offline_setup/python-3.13.14-amd64.exe` and compare it with INSTALLER_SHA256;
- require wheel filenames beginning with `openpyxl-`, `python_dotenv-`, and `et_xmlfile-`;
- parse `SHA256SUMS.txt` and require every `.exe` and `.whl` file to be listed exactly once;
- recalculate every listed file hash and require an exact lowercase match.
```

- [ ] **Step 2: 자산 테스트가 예상대로 실패하는지 확인**

Run:

```cmd
py -3.13 -B -m unittest tests.test_offline_setup -v
```

Expected: FAIL because the installer, wheelhouse, and hash manifest do not exist.

- [ ] **Step 3: Python 공식 오프라인 설치 파일 다운로드 및 검증**

Download only:

```text
https://www.python.org/ftp/python/3.13.14/python-3.13.14-amd64.exe
```

Save it as `offline_setup/python-3.13.14-amd64.exe`, then run:

```powershell
(Get-FileHash -LiteralPath '.\offline_setup\python-3.13.14-amd64.exe' -Algorithm SHA256).Hash.ToLowerInvariant()
```

Expected:

```text
c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0
```

Delete the file and stop if the hash differs.

- [ ] **Step 4: Windows x64/Python 3.13용 wheelhouse 생성**

Run from the project root:

```cmd
py -3.13 -m pip download --dest offline_setup\wheels --only-binary=:all: --platform win_amd64 --python-version 3.13 --implementation cp --abi cp313 -r requirements.txt
```

Expected: wheels for `openpyxl`, `python-dotenv`, `et_xmlfile`, and any resolver-selected transitive dependencies.

- [ ] **Step 5: 모든 오프라인 자산의 SHA-256 목록 생성**

Generate `offline_setup/SHA256SUMS.txt` in deterministic relative-path order with one line per asset:

```text
<lowercase sha256> *python-3.13.14-amd64.exe
<lowercase sha256> *wheels/<wheel filename>
```

- [ ] **Step 6: 목표 테스트 실행**

Run:

```cmd
py -3.13 -B -m unittest tests.test_offline_setup -v
```

Expected: all offline setup tests pass.

- [ ] **Step 7: 격리 환경에서 실제 오프라인 패키지 설치 검증**

Create a fresh temporary Python 3.13 virtual environment, then run:

```cmd
python -m pip install --no-index --find-links=offline_setup\wheels -r requirements.txt
python -c "import openpyxl, dotenv; print(openpyxl.__version__)"
```

Expected: install and imports succeed without accessing a package index. Resolve the temporary directory under the system temp directory before recursively removing only that verified temporary directory.

- [ ] **Step 8: 전체 프로젝트 테스트 실행**

Run:

```cmd
py -3.13 -B -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 9: 오프라인 자산과 테스트 커밋**

```cmd
git add tests/test_offline_setup.py offline_setup/python-3.13.14-amd64.exe offline_setup/wheels offline_setup/SHA256SUMS.txt
git commit -m "Bundle verified offline Python dependencies"
```
