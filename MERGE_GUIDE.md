# 기존 포털 병합 안내

## 기본 병합 대상

| 독립 프로젝트 파일 | 기존 포털 위치 | 용도 |
|---|---|---|
| `components/BusinessCardOrder.tsx` | `components/BusinessCardOrder.tsx` | 직원 신청·시안 화면 |
| `components/BusinessCardOrderAdmin.tsx` | `components/BusinessCardOrderAdmin.tsx` | 관리자 대시보드 |
| `services/businessCardOrderService.ts` | `services/businessCardOrderService.ts` | 프런트 API 계약 |
| `businessCardOrderServer.cjs` | `businessCardOrderServer.cjs` | 승인·저장·메일 발송 API |
| `tests/businessCardOrderServer.test.cjs` | `tests/businessCardOrderServer.test.cjs` | 서버 회귀 테스트 |

로고를 변경한 경우에만 `public/sidebar_logo.png`도 검토합니다.

## 병합하면 안 되는 독립 실행용 파일

- `App.tsx`, `index.tsx`, `index.html`
- `server.cjs`, `scripts/dev.cjs`
- `types.ts`, `vite.config.ts`
- `data/`, `uploads/`, `.env`
- `package.json` 전체 덮어쓰기

이 파일들은 팀원들이 명함발주 화면만 독립 실행하도록 만든 틀입니다.

## 권장 병합 순서

1. 기존 포털과 수정본의 위 5개 파일을 비교합니다.
2. 명함발주와 직접 관련된 변경만 기존 포털에 반영합니다.
3. 실제 `.env`와 SMTP 정보는 기존 운영 서버 설정을 유지합니다.
4. `node --test tests/businessCardOrderServer.test.cjs`를 실행합니다.
5. 기존 포털 전체 `npm run build`를 실행합니다.
6. 직원 신청, 관리자 승인·반려, 신청 이력을 다시 확인합니다.

DB 컬럼 변경이 생겼다면 소스 파일만 복사하지 말고 전산팀 검토 후 별도 SQL 마이그레이션으로 적용해야 합니다.
