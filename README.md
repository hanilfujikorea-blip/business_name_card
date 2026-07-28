# 명함 발주 메일 자동화

직원이 메일로 보낸 명함 신청 엑셀을 수집하고, 업체 발주 메일 초안을 만든 뒤 담당자가 로컬 포털에서 확인·승인하면 발송하는 사내 자동화 프로그램입니다.

## 처리 흐름

1. 지정한 메일함에서 제목에 정확한 부분 문자열 `명함`이 포함된 메일만 찾습니다. 첨부파일명은 대상 판정에 사용하지 않습니다.
2. `.xlsx` 또는 `.xlsm` 신청서를 `inbox/requests`에 저장합니다.
3. 이름을 포함한 핵심 헤더가 있는 명함 신청서만 분석합니다.
4. 발주 메일 초안과 미리보기, 대시보드를 생성합니다.
5. 담당자가 최종 확인 화면에서 수신자와 첨부파일을 확인합니다.
6. 승인된 메일을 건별로 발송하고 성공 해시와 결과를 즉시 저장합니다.

구형 `.xls` 파일은 지원하지 않습니다. `.xlsx` 형식으로 다시 저장해 접수해야 합니다.

## 설치

Python 3.11 이상을 권장합니다.

```powershell
py -m pip install -r requirements.txt
```

이 프로그램은 사내 메일 연동을 위해 상위 폴더의 `3. SOA_fup_sales/archive_mailer_api.py`도 사용합니다.

## 환경설정

`.env.example`을 참고해 프로젝트 루트에 `.env`를 만듭니다.

필수 항목:

- `ARCHIVE_BASE_URL`
- `ARCHIVE_USERNAME`
- `ARCHIVE_PASSWORD`
- `ARCHIVE_FROM_ADDRESS`
- `BUSINESS_CARD_MAILBOX_FOLDER`
- 업체 수신자는 `.env`의 `BUSINESS_CARD_VENDOR_TO` 또는 `inbox/vendor_mail_template.json` 중 한 곳에 설정

권장 항목:

- `BUSINESS_CARD_MAILBOX_KEYWORDS=명함`
- `BUSINESS_CARD_MONITOR_INTERVAL_SEC=60`
- `BUSINESS_CARD_REQUEST_SENDERS`: 신청서를 보낼 수 있는 사내 발신자 주소 목록

허용 발신자 목록이 비어 있으면 키워드 조건만 적용됩니다. 운영 환경에서는 발신자 목록도 설정하는 것을 권장합니다.

## 실행

가장 쉬운 방법은 다음 BAT 파일을 더블클릭하는 것입니다.

```text
run_business_card_mailer.bat
```

포털 주소는 `http://127.0.0.1:8765/`입니다. 포털은 이 PC에서만 접근할 수 있습니다.

CLI 명령:

```powershell
py -B business_card_mailer.py fetch
py -B business_card_mailer.py build
py -B business_card_mailer.py sync
py -B business_card_mailer.py monitor
py -B business_card_mailer.py dashboard
```

실제 발송 명령은 다음과 같지만, 평상시에는 포털의 최종 확인 화면을 사용하십시오.

```powershell
py -B business_card_mailer.py send --approve-send
```
## 운영 포털 사용 순서

1. `http://127.0.0.1:8765/`에서 운영 포털을 엽니다.
2. `기본 발송 설정`에서 업체의 받는 사람과 참조 주소를 입력합니다.
3. 주소가 여러 개라면 쉼표(`,`) 또는 세미콜론(`;`)으로 구분합니다.
4. `기본 발송 설정 저장`을 클릭합니다.
5. `직접 승인`에서는 발송 내용을 검토한 뒤 최종 발송 버튼을 눌러야 실제로 발송됩니다.
6. `자동 발송`으로 전환하면 확인창 승인 이후 새로 들어온 유효한 명함 메일만 즉시 발송됩니다. 자동 운영이 필요 없으면 `직접 승인`으로 다시 전환하십시오.
7. 제목에 정확한 부분 문자열 `명함`이 없는 메일은 첨부파일명과 관계없이 처리하지 않습니다.
8. 오류는 운영 포털과 대시보드의 `확인 필요` 및 발송 이력에서 확인합니다.

초기 운영 모드는 `직접 승인`입니다. 자동 발송 전환은 외부 업체로 즉시 발송될 수 있으므로 받는 사람, 참조, 제목, 본문과 첨부파일을 먼저 확인하십시오.

## 발송 안전장치

- 동기화와 발송은 같은 작업 잠금을 사용하므로 동시에 실행되지 않습니다.
- JSON은 임시 파일 작성 후 원자적으로 교체합니다.
- 수신자, 원본 파일 해시와 모든 첨부파일을 발송 직전에 다시 검사합니다.
- 한 건이 성공하면 다음 건의 성공 여부와 관계없이 발송 해시를 즉시 저장합니다.
- 포털 발송에는 CSRF 토큰과 현재 초안 digest가 필요합니다.
- 최종 확인 후 초안이 바뀌면 발송이 거부됩니다.

## 상태 복구

손상 JSON을 발견한 경우 먼저 포털을 종료한 뒤 다음 명령을 실행합니다.

```powershell
py -B recover_business_card_state.py
```

원본은 `output/backups/<timestamp>/`에 보존됩니다. 백업을 확인하기 전에는 `processed_state.json`을 삭제하거나 빈 파일로 바꾸지 마십시오. 이 파일의 발송 해시가 사라지면 과거 신청서가 다시 발송 대상이 될 수 있습니다.

## 테스트

테스트는 가짜 메일 클라이언트를 사용하며 실제 메일을 발송하지 않습니다.

```powershell
py -B -m unittest discover -s tests -v
```

## 개인정보 보관

`inbox/requests`와 `output`에는 이름, 연락처, 이메일, 신청서 원본과 발송 이력이 포함될 수 있습니다.

- 조직의 개인정보 보관 기간과 삭제 승인 절차를 따르십시오.
- 이 프로그램은 예기치 않은 데이터 손실을 막기 위해 자동 삭제를 수행하지 않습니다.
- `.env`, 신청서, 출력 JSON과 백업 파일은 Git에 포함하지 마십시오.
- 폴더 접근 권한은 실제 담당자에게만 부여하십시오.

## 주요 파일

- `business_card_mailer.py`: 메일 수집, 엑셀 분석, 초안과 발송 CLI
- `business_card_portal.py`: 로컬 승인 포털
- `business_card_storage.py`: 원자적 JSON 저장, 복구, 작업 잠금
- `business_card_sending.py`: 발송 직전 검증과 건별 결과 저장
- `business_card_portal_security.py`: CSRF 및 초안 digest 검증
- `inbox/request_sheet_mapping.json`: 엑셀 헤더 매핑과 판별 기준
- `inbox/vendor_mail_template.json`: 업체 수신자와 메일 템플릿

## 메일 편집 및 발송

대시보드의 `발송 내용 검토`에서 수신, 참조, 제목과 인사말·요청 문구·맺음말을 확인하고 수정할 수 있습니다. 신청자와 발주 정보 표는 자동 생성 영역이므로 편집되지 않습니다.

- `이번 발송에만 저장`: 선택한 초안의 수정값을 `output/business_card_send_overrides.json`에 저장합니다.
- `수신·참조·문구 전체 적용`: 준비된 모든 초안에 공통값을 적용하되 각 메일의 제목은 유지합니다.
- `기본값으로 저장`: 이후 자동발주에 사용할 수신·참조·문구를 `inbox/vendor_mail_template.json`에 저장하며 제목 템플릿은 변경하지 않습니다.
- 임시 수정값은 `draft_id`와 원본 신청서의 `source_hash`가 모두 일치할 때만 적용됩니다.
- 수신·참조·제목·최종 본문·첨부파일 중 하나라도 바뀌면 기존 발송 승인은 무효가 되어 다시 확인해야 합니다.
