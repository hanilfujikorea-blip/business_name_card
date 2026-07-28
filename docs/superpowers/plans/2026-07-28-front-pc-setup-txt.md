# Front PC Setup TXT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a concise Korean TXT checklist with every CMD command needed to install dependencies, synchronize once, run the portal, and manage automatic startup.

**Architecture:** Create one UTF-8 text file in the project root. Use the approved absolute path and existing commands without changing configuration or application code.

**Tech Stack:** Windows CMD, Python 3.13, pip, project BAT launcher, schtasks

## Global Constraints

- Create `앞자리PC_설치_실행.txt`.
- Use `C:\Users\Felix\2026.06.24\홍은기\4. business_card_order_mailer` in every project command.
- Existing `.env`, inbox settings, output state, and mail-module values remain unchanged.
- Include install, test, sync, run, automatic-start create/query/stop/restart commands.
- Include no password, token, or actual email address.
- Do not run `monitor` alongside the portal.
- Stop the previous PC process before starting the new PC process.

---

### Task 1: Create and verify the setup checklist

**Files:**
- Create: `앞자리PC_설치_실행.txt`
- Reference: `run_business_card_mailer.bat`
- Reference: `.env.example`

**Interfaces:**
- Consumes: the fixed project path and current CLI/BAT commands.
- Produces: one copy-pasteable operator checklist.

- [ ] **Step 1: Prove the artifact is absent**

Run `Test-Path -LiteralPath '앞자리PC_설치_실행.txt'` and expect `False`.

- [ ] **Step 2: Create the TXT with the approved installation, test, synchronization, portal, and scheduled-task commands**

State first: stop the old PC, then copy the project, unchanged `.env`, inbox/output state, and `archive_mailer_api.py`.

```cmd
where py
winget install -e --id Python.Python.3.13
cd /d "C:\Users\Felix\2026.06.24\홍은기\4. business_card_order_mailer"
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

Add test, first synchronization, portal run, and browser-open commands:

```cmd
py -B -m unittest discover -s tests -v
py -B business_card_mailer.py sync
run_business_card_mailer.bat
start "" http://127.0.0.1:8765/
```

Add scheduled-task creation and management commands:

```cmd
schtasks /Create /TN "KGroupBusinessCardPortal" /SC ONLOGON /DELAY 0000:30 /TR "'C:\Users\Felix\2026.06.24\홍은기\4. business_card_order_mailer\run_business_card_mailer.bat'" /RL LIMITED /F
schtasks /Run /TN "KGroupBusinessCardPortal"
schtasks /Query /TN "KGroupBusinessCardPortal" /V /FO LIST
netstat -ano | findstr :8765
schtasks /End /TN "KGroupBusinessCardPortal"
schtasks /Run /TN "KGroupBusinessCardPortal"
```

End with a check of existing recipient/copy/text values and manual synchronization before switching the portal to automatic mode.

- [ ] **Step 3: Verify required and safe content**

Assert that the TXT contains the fixed path, install/test/sync/run commands, all four `schtasks` actions, and the portal URL. Scan for assigned secrets, email patterns, and unfinished markers; expected count for every category is `0`.

- [ ] **Step 4: Verify scope and commit**

Run `git status --short`; only the TXT may be new. Then run:

```cmd
git add -- "앞자리PC_설치_실행.txt"
git commit -m "Add front PC setup checklist"
```
