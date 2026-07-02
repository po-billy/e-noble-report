# 배포 매뉴얼 — 광고 보고서B 자동화 (ad-report)

실제 서버에 올릴 때의 **환경변수 · 인프라 세팅** 가이드입니다.
로그인 → 광고주 등록 → 보고서B 생성/다운로드가 팀장별로 격리 동작하는 웹앱을 배포합니다.

---

## 1. 아키텍처 한눈에

```
[브라우저] ──HTTPS──> [Nginx :443] ──proxy──> [uvicorn :8000 (FastAPI)]
                                                   │
                                                   ├─ 네이버 검색광고 API (GET 조회)
                                                   ├─ Claude API (AI 코멘트)
                                                   └─ 로컬 파일: data/app.db · output/*.xlsx · uploads/
```

- **앱 실행**: `uvicorn web.app:app` (포트 8000)
- **DB**: SQLite `data/app.db` (사용자·광고주·보고서)
- **산출물**: `output/*.xlsx`, 업로드 임시파일 `uploads/`
- **생성 작업**: 서버 백그라운드(asyncio) — 요청 후 브라우저가 나가도 개별 생성은 완료됨

---

## 2. 서버 스펙 권장 (광고주 ~500 기준)

| 항목 | 권장 | 비고 |
|---|---|---|
| CPU / RAM | **4 vCPU / 8GB** | 동시 생성 4건 + 웹 여유. 최소 2vCPU/4GB(동시 2건) |
| 디스크 | **40~80GB SSD** | 보고서 1건 ~2MB · 월 500건 ≈ 1GB. 몇 달 보관 여유 |
| OS | Ubuntu 22.04 LTS | (또는 Docker 지원 리눅스) |
| Python | **3.11** | Dockerfile 기준 |
| 네트워크 | 아웃바운드 443 | 네이버·Claude API 호출 |

> 비용 개략: 국내 클라우드 4vCPU/8GB 월 ₩9~13만 + Claude API(코멘트, 건수 비례) ₩2~5만.

---

## 3. 환경변수 (`.env`)

프로젝트 루트에 `.env` 파일을 만듭니다. **절대 git/외부에 커밋 금지.**
`.env.example`을 복사해서 채우세요: `cp .env.example .env`

### 필수

| 변수 | 설명 | 예시 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API 키 (AI 코멘트 생성) | `sk-ant-api03-...` |
| `SESSION_SECRET` | 로그인 세션 쿠키 서명 키. **반드시 임의의 긴 문자열로 변경** | `openssl rand -hex 32` 결과 |
| `NAVER_MOCK` | `false` = 실 네이버 API, `true` = 가짜데이터(테스트) | `false` |

### 선택 (필요 시)

| 변수 | 설명 | 기본 |
|---|---|---|
| `NAVER_API_KEY` / `NAVER_API_SECRET` / `NAVER_CUSTOMER_ID` / `NAVER_ACCOUNT_NAME` | 단일 계정 **폴백**용. 키는 보통 웹 UI/시트로 광고주별 등록하므로 **비워도 됨** | 빈값 |
| `ROSTER_GSHEET_ID` | Google Sheets를 로스터 원본으로 쓸 때 시트 ID | 빈값(→ 로컬 xlsx) |
| `ROSTER_GSHEET_TAB` | 위 시트의 탭 이름 | 첫 탭 |
| `GOOGLE_APPLICATION_CREDENTIALS` | gspread용 서비스계정 JSON 경로 (Sheets 연동 시) | 빈값 |

> `REPORT_PASSWORD`는 현재 코드에서 사용하지 않습니다(레거시). 무시하세요.

### 보안 주의
- `NAVER_MOCK=false`이고 등록된 계정이 하나도 없으면 자동으로 MOCK 모드가 됩니다. 실 운영은 웹에서 광고주+키를 등록하거나 폴백 `.env` 키를 넣으세요.
- `.env`, `data/app.db`, `accounts.json` 은 **키·개인정보 포함** → 저장소/백업 접근권한 제한, 평문 커밋 금지.

---

## 4. 배포 방법 A — 직접(systemd) 설치

가장 단순한 단일 서버 방식입니다.

```bash
# 0) 코드 배치
git clone <repo> ad-report && cd ad-report     # 또는 파일 업로드

# 1) 파이썬 가상환경
python3.11 -m venv .venv && source .venv/bin/activate

# 2) 의존성
pip install -r requirements.txt

# 3) 환경변수
cp .env.example .env && nano .env              # 필수 3개 채우기

# 4) 폴더 준비 + systemd 등록 (제공 스크립트)
bash deploy.sh
```

`deploy.sh`가 하는 일: 의존성 설치 → `uploads/ output/` 생성 → `.env` 확인 → **systemd 서비스 `ad-report`** 등록(포트 8000, `Restart=always`).

```bash
systemctl status ad-report      # 상태
journalctl -u ad-report -f      # 로그 실시간
systemctl restart ad-report     # 재시작
```

> `deploy.sh`는 `User=ubuntu`로 등록합니다. 계정이 다르면 파일의 `User=` 를 수정하세요.
> **워커는 1개(기본)로 유지하세요.** 생성 진행상태(job)를 메모리에 두므로 멀티워커면 진행률 폴링이 어긋날 수 있습니다(완료/실패는 DB로 조회되어 표시는 됨).

---

## 5. 배포 방법 B — Docker

```bash
# 이미지 빌드
docker build -t ad-report .

# 실행 (.env 주입 + 데이터 볼륨 마운트로 영속화)
docker run -d --name ad-report --restart always \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/uploads:/app/uploads \
  ad-report
```

- **볼륨 마운트 필수**: `data/`(DB), `output/`(보고서), `uploads/`를 호스트에 매핑해야 컨테이너 재생성/업데이트 시에도 데이터가 유지됩니다.
- 로그: `docker logs -f ad-report`

---

## 6. Nginx + HTTPS (리버스 프록시)

제공된 `nginx.conf` 예시(도메인 `report.crama.app`)를 참고합니다.

```bash
# 1) 사이트 설정 배치 (도메인만 본인 것으로 수정)
sudo cp nginx.conf /etc/nginx/sites-available/ad-report
sudo ln -s /etc/nginx/sites-available/ad-report /etc/nginx/sites-enabled/

# 2) 무료 SSL 발급 (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d report.your-domain.com

# 3) 문법 검사 후 재시작
sudo nginx -t && sudo systemctl reload nginx
```

핵심 설정(이미 예시에 포함):
- `:443` → `proxy_pass http://127.0.0.1:8000`
- `client_max_body_size 50M` (시트 업로드 여유)
- `proxy_read_timeout 120s` (생성 요청 여유)

---

## 7. 최초 실행 후 세팅

1. 브라우저에서 `https://<도메인>` 접속 → **자동으로 `/setup`** (사용자 0명일 때)
2. **관리자 계정** 생성 (이름·이메일·비밀번호 8자↑)
3. 로그인 → 팀장 계정은 **[팀원 관리]**(관리자 전용)에서 추가
4. 각 팀장이 로그인 → **[광고주 · 생성]** 에서 시트 업로드 또는 개별 추가로 광고주+API키 등록
5. 연·월 선택 → 생성 → **[생성된 보고서]** 에서 개별/일괄(zip) 다운로드

> 격리 규칙: 팀장/팀원은 **자기 광고주·보고서만**, 관리자는 전체를 봅니다.

---

## 8. 데이터 영속성 & 백업

| 경로 | 내용 | 백업 |
|---|---|---|
| `data/app.db` | 사용자·광고주(키 포함)·보고서 메타 | **정기 백업 필수** |
| `output/` | 생성된 xlsx 보고서 | 재생성 가능하나 보관 권장 |
| `uploads/` | 업로드 임시파일·zip | 불필요(정리 가능) |

간단 백업 예:
```bash
# 매일 새벽 app.db 스냅샷 (cron)
0 4 * * * cp /path/ad-report/data/app.db /backup/app_$(date +\%F).db
```

---

## 9. 업데이트 배포

```bash
cd ad-report
git pull                                  # 또는 새 파일 반영
source .venv/bin/activate
pip install -r requirements.txt           # 의존성 변경 시
systemctl restart ad-report               # (Docker면: docker build 후 재run)
```

- DB 스키마 변경은 앱 시작 시 **자동 마이그레이션**(`init_db`)됩니다. 기존 데이터는 보존됩니다.
- 배포 전 `data/app.db` 백업을 권장합니다.

---

## 10. 트러블슈팅

| 증상 | 확인 |
|---|---|
| 로그인/생성 안 됨 | `journalctl -u ad-report -f` 로그 확인 |
| 전부 MOCK 데이터로 나옴 | `.env`의 `NAVER_MOCK=false` 인지, 광고주에 키가 등록됐는지 |
| 생성 실패(수집 실패) | 해당 광고주 `api_key/secret/customer_id` 정확한지, 서버 시계 동기화(네이버 서명 만료 방지) |
| 코멘트 실패 | `ANTHROPIC_API_KEY` 유효한지 |
| 업로드 413 에러 | Nginx `client_max_body_size` 상향 |
| 생성 진행률이 안 보임 | 워커 1개인지 확인(멀티워커 시 폴링 어긋남) |

---

## 11. 보안 체크리스트 (운영 전)

- [ ] `SESSION_SECRET` 를 임의 강한 값으로 변경했는가
- [ ] HTTPS(certbot) 적용했는가
- [ ] `.env` / `data/app.db` / `accounts.json` 접근권한 제한(600), 저장소 미커밋
- [ ] `NAVER_MOCK=false` (실 운영)
- [ ] `data/app.db` 정기 백업 설정
- [ ] (선택) API 키는 코드/시트 평문 대신 환경변수·암호화 저장으로 이전 검토
```
