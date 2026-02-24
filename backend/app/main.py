import asyncio
from contextlib import asynccontextmanager
import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from arq import create_pool
from arq.connections import RedisSettings
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import settings
from .limiter import limiter
from .localization import localize_json_bytes
from .routers import forecast, health, natal, tarot, telemetry, tasks as tasks_router, users
try:
    from .routers import geo
except ImportError:  # pragma: no cover
    geo = None
try:
    from .routers import numerology as numerology_router
except ImportError:  # pragma: no cover
    numerology_router = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    force=True,
)
logger = logging.getLogger("astrobot.api")


def _truncate(text: str, limit: int = 900) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated]"


def _body_preview(raw: bytes, content_type: str) -> str:
    if not raw:
        return "-"
    if "application/json" in content_type:
        try:
            parsed = json.loads(raw.decode("utf-8"))
            return _truncate(json.dumps(parsed, ensure_ascii=False, separators=(",", ":")))
        except Exception:
            return _truncate(raw.decode("utf-8", errors="replace"))
    return f"<{len(raw)} bytes; {content_type or 'unknown'}>"


class ApiAuditAndLocalizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = uuid4().hex[:8]
        started_at = time.perf_counter()

        request_content_type = request.headers.get("content-type", "")
        content_length = int(request.headers.get("content-length", 0) or 0)
        # Only buffer request body for logging if small enough (avoid OOM on large uploads)
        if content_length <= 102400:  # 100 KB
            request_body = await request.body()
        else:
            request_body = b""
        request_preview = _body_preview(request_body, request_content_type)

        method = request.method
        path = request.url.path
        query = request.url.query
        full_path = f"{path}?{query}" if query else path
        tg_user_id = request.headers.get("x-tg-user-id") or "-"
        auth_mode = "telegram" if request.headers.get("x-telegram-init-data") else "dev/internal"

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.exception(
                "API %s %s | status=500 | user=%s | auth=%s | t=%.1fms | req=%s | req_id=%s",
                method,
                full_path,
                tg_user_id,
                auth_mode,
                elapsed_ms,
                request_preview,
                request_id,
            )
            raise

        response_content_type = response.headers.get("content-type", "")
        response_body = b""
        body_size = 0
        async for chunk in response.body_iterator:
            body_size += len(chunk)
            response_body += chunk

        localized_body = response_body
        if (
            settings.enable_response_localization
            and response.status_code not in (204, 304)
            and "application/json" in response_content_type
        ):
            # Run sync (potentially blocking) localization in a threadpool thread
            # to avoid blocking the event loop during Google Translate HTTP calls.
            localized_body = await asyncio.to_thread(localize_json_bytes, response_body)

        response_preview = _body_preview(localized_body, response_content_type)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "API %s %s | status=%s | user=%s | auth=%s | t=%.1fms | req=%s | resp=%s | req_id=%s",
            method,
            full_path,
            response.status_code,
            tg_user_id,
            auth_mode,
            elapsed_ms,
            request_preview,
            response_preview,
            request_id,
        )

        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(
            content=localized_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


logging.getLogger("uvicorn.access").disabled = True
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize ARQ connection pool for enqueueing background LLM jobs
    try:
        arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        app.state.arq_pool = arq_pool
        logger.info("ARQ pool connected to %s", settings.redis_url)
    except Exception as exc:
        logger.warning("ARQ pool unavailable (Redis down?): %s — LLM endpoints will use fallback", exc)
        app.state.arq_pool = None

    yield

    if getattr(app.state, "arq_pool", None) is not None:
        await app.state.arq_pool.close()


app = FastAPI(title="AstroBot API", version="0.2.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.add_middleware(SlowAPIMiddleware)
app.add_middleware(ApiAuditAndLocalizationMiddleware)

if settings.cors_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-TG-User-Id", "X-Telegram-Init-Data", "X-Internal-Api-Key"],
    )

app.include_router(health.router)
if geo is not None:
    app.include_router(geo.router)
app.include_router(natal.router)
app.include_router(forecast.router)
app.include_router(tarot.router)
app.include_router(telemetry.router)
app.include_router(users.router)
app.include_router(tasks_router.router)
if numerology_router is not None:
    app.include_router(numerology_router.router)
