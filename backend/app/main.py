from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import compat, forecast, health, natal, tarot, wishlist


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
