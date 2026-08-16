# API Rate Limiter Service

FastAPI 기반 API 요청 제한(Rate Limiting) 서비스 스켈레톤.
Token Bucket 알고리즘 + 메신저 채널(Slack/Discord/Telegram) 웹훅 알림.

> Redis가 없어도 **인메모리 백엔드로 자동 폴백**하여 바로 실행됩니다.

## 구조

```
o/
├─ main.py              # FastAPI 진입점, 예외 핸들러, /health, /demo
├─ requirements.txt
├─ .env.example
└─ app/
   ├─ config.py         # 환경 변수 설정
   ├─ models.py         # 요청/응답·정책 Pydantic 모델
   ├─ policies.py       # 요금제별 정책 저장소
   ├─ identify.py       # 클라이언트 식별 (API Key / IP)
   ├─ limiter.py        # Token Bucket (인메모리 / Redis Lua)
   ├─ notifier.py       # 메신저 웹훅 알림 (쿨다운 포함)
   └─ api.py            # /v1 라우터 + rate_limit 의존성
```

## 실행

```bash
# 1) 의존성 설치 (전체 기능)
py -m pip install -r requirements.txt

# 2) (선택) 환경 변수 설정
copy .env.example .env    # 필요 시 편집

# 3) 서버 실행
py -m uvicorn main:app --reload
```

- API 문서(Swagger): http://127.0.0.1:8000/docs
- 상태 확인: http://127.0.0.1:8000/health

> 최소 실행만 원하면 `py -m pip install fastapi "uvicorn[standard]"` 만으로도
> 동작합니다(redis/httpx는 각각 Redis 백엔드·알림 전송 시에만 필요).

## 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/v1/check` | 요청 허용 여부 판정 |
| GET | `/v1/usage/{client_id}` | 사용량/잔여량 조회 |
| GET | `/v1/policies` | 정책 목록 조회 |
| PUT | `/v1/policies` | 정책 등록/수정 |
| GET | `/health` | 상태 확인 |
| GET | `/demo` | rate limit 적용 예시 라우트 |

### 예시

```bash
# 허용 여부 판정 (Pro 요금제 키)
curl -X POST http://127.0.0.1:8000/v1/check \
  -H "X-API-Key: demo-pro-key" -H "Content-Type: application/json" \
  -d '{"endpoint": "search"}'

# 보호된 라우트 반복 호출로 429 유도 (무료/IP 기준)
curl -i http://127.0.0.1:8000/demo
```

## 테스트

```bash
# 1) 테스트 의존성 설치 (pytest 포함)
py -m pip install -r requirements-dev.txt

# 2) 전체 테스트 실행 (프로젝트 루트 o/ 에서)
py -m pytest
```

`tests/` 구성:

| 파일 | 검증 대상 |
|------|-----------|
| `test_limiter.py` | Token Bucket 허용/차단·시간 리필·peek(소비 없음)·key 격리 |
| `test_identify.py` | API Key→요금제 매핑, IP 폴백, explicit_id 우선순위 |
| `test_notifier.py` | 채널별 enabled 판정, 쿨다운 디바운스, 전송 실패 흡수 |
| `test_api.py` | `/health`·`/v1/*`·`/demo` 통합, 429 헤더, 입력 검증(422) |

> 외부 의존성(Redis·웹훅) 없이 인메모리 백엔드로 동작하므로 그대로 실행 가능합니다.

## 알림 연동

`.env`에서 채널을 지정하면 제한 초과 등 이벤트 발생 시 웹훅으로 알림을 보냅니다.

```
NOTIFY_CHANNEL=slack
NOTIFY_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

Discord는 채널 Webhook URL, Telegram은 `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`를 사용합니다.
동일 이벤트는 `NOTIFY_COOLDOWN`(초) 동안 중복 발송되지 않습니다.

## 확장 포인트

- `identify.py` : API Key→요금제 매핑을 DB/Redis 조회로 교체
- `policies.py` : 정책을 영속 저장소에 보관하고 동적 로드
- `notifier.py` : 전송 실패 재시도·백업, 채널 추가 (Notifier 인터페이스화)
- `limiter.py`  : Sliding Window 등 다른 알고리즘 백엔드 추가
