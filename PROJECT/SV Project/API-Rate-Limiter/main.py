"""API Rate Limiter Service — FastAPI 진입점.

실행:
    py -m uvicorn main:app --reload

Redis가 없어도 인메모리 백엔드로 자동 폴백하여 동작한다.
문서: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from app.api import rate_limit, router
from app.config import settings
from app.limiter import RateLimitExceeded, build_limiter
from app.notifier import Notifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ratelimiter")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.limiter = await build_limiter(settings.redis_url)
    app.state.notifier = Notifier(settings)
    logger.info("Rate limiter backend : %s", type(app.state.limiter).__name__)
    logger.info(
        "Notifier             : enabled=%s channel=%s",
        app.state.notifier.enabled,
        settings.notify_channel,
    )
    try:
        yield
    finally:
        await app.state.limiter.close()


# Swagger UI 문서 화면의 태그(섹션) 순서 및 한국어 설명
_TAGS_METADATA = [
    {"name": "요청 제한", "description": "요청 허용 판정과 요금제 정책 관리 엔드포인트"},
    {"name": "시스템", "description": "서비스 상태 및 사용 중인 백엔드 확인"},
    {"name": "예시", "description": "rate limit이 적용된 예시 라우트"},
]

app = FastAPI(
    title="API Rate Limiter 서비스",
    version="0.1.0",
    description=(
        "클라이언트의 과도한 API 호출을 제어(요청 제한)하여 서버 자원을 보호하는 "
        "백엔드 서비스입니다.\n\n"
        "- **알고리즘**: Token Bucket (버스트 허용 + 평균 속도 제어)\n"
        "- **백엔드**: Redis가 없으면 인메모리로 자동 폴백\n"
        "- **클라이언트 식별**: `X-API-Key` 헤더 우선, 없으면 소스 IP\n\n"
        "각 엔드포인트를 펼친 뒤 **[요청 보내보기]** 버튼으로 직접 호출해볼 수 있습니다."
    ),
    openapi_tags=_TAGS_METADATA,
    lifespan=lifespan,
    docs_url=None,  # 기본 영어 문서 대신 아래 한국어 커스텀 문서를 사용
)
app.include_router(router)


# ── Swagger UI 버튼/라벨을 한국어로 치환하는 스크립트 ────────────────────
# Swagger UI 자체는 영어 UI만 제공하므로, 렌더링된 화면의 고정 라벨 텍스트를
# 사전(dict) 기반으로 바꿔준다. 입력 필드(INPUT/TEXTAREA)는 건드리지 않는다.
_KOREAN_DOCS_SCRIPT = """
<script>
(function () {
  var dict = {
    "Try it out": "요청 보내보기", "Cancel": "취소", "Execute": "실행",
    "Clear": "초기화", "Reset": "초기화", "Parameters": "파라미터",
    "No parameters": "파라미터 없음", "Name": "이름", "Description": "설명",
    "Request body": "요청 본문", "Responses": "응답", "Response body": "응답 본문",
    "Server response": "서버 응답", "Responses samples": "응답 예시", "Code": "코드",
    "Details": "상세", "Media type": "미디어 타입", "Example Value": "예시 값",
    "Schema": "스키마", "Schemas": "스키마", "Download": "다운로드",
    "Authorize": "인증", "Available authorizations": "사용 가능한 인증",
    "Close": "닫기", "Request URL": "요청 URL", "Loading...": "불러오는 중...",
    "required": "필수", "Links": "링크", "No links": "링크 없음",
    "Send empty value": "빈 값 보내기", "Expand all": "모두 펼치기",
    "Collapse all": "모두 접기", "Copy to clipboard": "클립보드에 복사",
    "Successful Response": "성공 응답", "Validation Error": "검증 오류",
    "Error": "오류", "Warning": "경고", "Deprecated": "지원 중단됨",
    "Controls": "제어 대상:", "header.": "헤더", "Accept": "Accept",
    "Edit Value": "값 수정", "Model": "모델", "Servers": "서버",
    "Query": "쿼리", "Path": "경로", "Header": "헤더",
    "Filter by tag": "태그로 필터", "No parameters.": "파라미터 없음"
  };
  function translate(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var nodes = [], n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function (node) {
      var t = (node.nodeValue || "").trim();
      var parent = node.parentNode;
      if (!parent) return;
      if (/^(INPUT|TEXTAREA|SCRIPT|STYLE|CODE|PRE)$/.test(parent.tagName)) return;
      if (dict[t]) node.nodeValue = node.nodeValue.replace(t, dict[t]);
    });
  }
  var obs = new MutationObserver(function () { translate(document.body); });
  window.addEventListener("load", function () {
    setTimeout(function () {
      translate(document.body);
      obs.observe(document.body, { childList: true, subtree: true });
    }, 300);
  });
})();
</script>
"""


@app.get("/docs", include_in_schema=False)
async def korean_swagger_ui() -> HTMLResponse:
    """기본 Swagger UI에 한국어 라벨 치환 스크립트를 주입한 문서 화면."""
    base = get_swagger_ui_html(openapi_url=app.openapi_url, title=f"{app.title} - API 문서")
    html = base.body.decode().replace("</body>", _KOREAN_DOCS_SCRIPT + "</body>")
    return HTMLResponse(html)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    r = exc.result
    headers = {
        "Retry-After": str(int(r.retry_after) + 1),
        "X-RateLimit-Limit": str(r.limit),
        "X-RateLimit-Remaining": str(r.remaining),
    }
    return JSONResponse(
        status_code=429,
        headers=headers,
        content={
            "error": "rate_limit_exceeded",
            "message": "요청 한도를 초과했습니다. 잠시 후 다시 시도하세요.",
            "client_id": exc.client_id,
            "retry_after": round(r.retry_after, 3),
        },
    )


@app.get(
    "/health",
    tags=["시스템"],
    summary="상태 확인",
    responses={200: {"description": "서비스 정상 (status / backend 반환)"}},
)
async def health(request: Request) -> dict[str, object]:
    """서비스 상태 및 사용 중인 백엔드 확인."""
    limiter = request.app.state.limiter
    return {"status": "ok", "backend": type(limiter).__name__}


# ── 예시: rate limit으로 보호되는 실제 엔드포인트 ───────────────────────
@app.get(
    "/demo",
    tags=["예시"],
    summary="요청 제한 예시 라우트",
    responses={
        200: {"description": "요청 허용됨"},
        429: {"description": "요청 한도 초과 (Retry-After 헤더 포함)"},
    },
)
async def demo(_rl=Depends(rate_limit(endpoint="demo"))) -> dict[str, str]:
    return {"message": "요청이 허용되었습니다 🎉"}
