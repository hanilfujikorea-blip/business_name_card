# Python WinGet Certificate Error Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 앞자리 PC 설치 안내서가 Microsoft Store 소스를 조회하지 않고 Python을 설치하도록 수정하고 인증서 오류 대응을 안내한다.

**Architecture:** 기존 TXT 한 파일의 Python 설치 구간만 최소 수정한다. 새 설치 명령은 WinGet 커뮤니티 저장소를 명시하며, 동일 오류가 계속될 때는 회사 PC 인증서 또는 보안 프록시 점검이 필요함을 안내한다.

**Tech Stack:** Windows CMD, WinGet, plain text documentation

## Global Constraints

- 수정 대상은 `앞자리PC_설치_실행.txt` 하나뿐이다.
- 애플리케이션 설정, 메일 주소, 환경 변수, 실행 명령은 변경하지 않는다.
- 이메일 주소, 비밀번호, 토큰 등 민감정보를 추가하지 않는다.
- Python 패키지 ID는 `Python.Python.3.13`을 유지한다.

---

### Task 1: Python 설치 및 인증서 오류 안내 수정

**Files:**
- Modify: `앞자리PC_설치_실행.txt:15`
- Test: `앞자리PC_설치_실행.txt`

**Interfaces:**
- Consumes: Windows CMD의 `winget` 명령
- Produces: 앞자리 PC 작업자가 위에서 아래로 실행할 수 있는 설치 안내

- [ ] **Step 1: 현재 안내가 새 명령 검사를 통과하지 못하는지 확인**

Run:

```powershell
$text = Get-Content -LiteralPath '.\앞자리PC_설치_실행.txt' -Raw
if ($text.Contains('--source winget') -and $text.Contains('0x80072f0d')) { exit 0 } else { exit 1 }
```

Expected: exit code `1` because the current guide does not contain the source restriction or error guidance.

- [ ] **Step 2: 설치 명령과 오류 대응 문구 수정**

Replace the existing command with:

```cmd
winget install -e --id Python.Python.3.13 --source winget --accept-source-agreements --accept-package-agreements
```

Add immediately below it:

```text
위 명령은 Microsoft Store를 제외하고 WinGet 저장소만 사용한다.
같은 0x80072f0d 오류가 다시 나오면 회사 PC의 인증서 또는 보안 프록시 문제이므로 오류 화면을 전산 담당자에게 전달한다.
```

- [ ] **Step 3: 안내 내용 검사**

Run:

```powershell
$text = Get-Content -LiteralPath '.\앞자리PC_설치_실행.txt' -Raw
$required = @('--source winget', '--accept-source-agreements', '--accept-package-agreements', '0x80072f0d', '인증서 또는 보안 프록시')
$old = 'winget install -e --id Python.Python.3.13' + [Environment]::NewLine + [Environment]::NewLine
$missing = @($required | Where-Object { -not $text.Contains($_) })
if ($missing.Count -eq 0 -and -not $text.Contains($old)) { exit 0 } else { exit 1 }
```

Expected: exit code `0`.

- [ ] **Step 4: 프로젝트 회귀 테스트 실행**

Run:

```cmd
py -B -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 5: 변경 사항 커밋**

```cmd
git add "앞자리PC_설치_실행.txt"
git commit -m "Fix Python winget install instructions"
```
