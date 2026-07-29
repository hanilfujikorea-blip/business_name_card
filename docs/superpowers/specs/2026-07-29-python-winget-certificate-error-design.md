# Python WinGet 인증서 오류 안내 개선 설계

## 목적

앞자리 PC에서 Python 설치 중 Microsoft Store 소스의 인증서 검증 오류 `0x80072f0d`가 발생하지 않도록 기존 설치 안내를 보완한다.

## 변경 범위

- 기존 `앞자리PC_설치_실행.txt`만 수정한다.
- Python 설치 명령에 `--source winget`을 지정해 Microsoft Store 소스를 조회하지 않도록 한다.
- 소스 및 패키지 약관 승인 옵션을 명시해 설치 중 불필요한 입력을 줄인다.
- 동일 오류가 계속될 경우 회사 PC의 인증서 또는 보안 프록시 문제임을 알리고 전산 담당자에게 문의하도록 안내한다.
- 애플리케이션 설정, 메일 주소, 환경 변수, 실행 명령은 변경하지 않는다.

## 적용 명령

```cmd
winget install -e --id Python.Python.3.13 --source winget --accept-source-agreements --accept-package-agreements
```

## 검증 기준

- 기존의 소스 미지정 Python 설치 명령이 남아 있지 않는다.
- 새 설치 명령과 `0x80072f0d` 대응 문구가 안내서에 포함된다.
- 이메일 주소, 비밀번호, 토큰 등 민감정보가 추가되지 않는다.
- 프로젝트의 기존 전체 테스트가 통과한다.
