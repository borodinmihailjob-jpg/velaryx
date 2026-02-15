from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import compat, forecast, health, natal, tarot, wishlist


class HealthAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return '"GET /health HTTP/' not in message


uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(HealthAccessFilter())


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="AstroBot API", version="0.2.0", lifespan=lifespan)

if settings.cors_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health.router)
app.include_router(natal.router)
app.include_router(forecast.router)
app.include_router(tarot.router)
app.include_router(compat.router)
app.include_router(wishlist.router)
