from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .config import settings
from .localization import localize_json_bytes
from .routers import compat, forecast, health, natal, tarot, wishlist
try:
    from .routers import geo
except ImportError:  # pragma: no cover
    geo = None


class HealthAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return '"GET /health HTTP/' not in message


class ResponseLocalizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if not settings.enable_response_localization:
            return response
        if response.status_code in (204, 304):
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        localized = localize_json_bytes(body)
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(
            content=localized,
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )


uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(HealthAccessFilter())


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="AstroBot API", version="0.2.0", lifespan=lifespan)
app.add_middleware(ResponseLocalizationMiddleware)

if settings.cors_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health.router)
if geo is not None:
    app.include_router(geo.router)
app.include_router(natal.router)
app.include_router(forecast.router)
app.include_router(tarot.router)
app.include_router(compat.router)
app.include_router(wishlist.router)
