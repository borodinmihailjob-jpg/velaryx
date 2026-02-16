"""
FastAPI proxy для Ollama с health checks и error handling.

Этот сервис:
- Проксирует запросы к локальному Ollama
- Предоставляет /health endpoint для мониторинга
- Логирует все запросы для debugging
- Обрабатывает ошибки gracefully
"""
import logging
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("ollama-proxy")

app = FastAPI(title="Ollama Proxy", version="1.0.0")

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 120.0


@app.get("/")
async def root():
    """Root endpoint для проверки что proxy работает."""
    return {
        "service": "ollama-proxy",
        "status": "running",
        "ollama_url": OLLAMA_BASE_URL,
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint для мониторинга доступности Ollama.

    Returns:
        200: Ollama доступен и отвечает
        503: Ollama недоступен
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/version")
            response.raise_for_status()

            version_data = response.json()

            return {
                "status": "healthy",
                "ollama": "available",
                "version": version_data.get("version", "unknown"),
            }
    except httpx.TimeoutException:
        logger.error("Health check timeout: Ollama не отвечает")
        raise HTTPException(
            status_code=503,
            detail="Ollama timeout - сервис недоступен",
        )
    except httpx.RequestError as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Ollama недоступен: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in health check: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Неожиданная ошибка: {str(e)}",
        )


@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request):
    """
    Проксирует OpenAI-compatible chat completions к Ollama.

    Ollama поддерживает OpenAI API format начиная с версии 0.1.14.
    """
    started_at = time.time()

    try:
        # Читаем body от клиента
        body = await request.json()

        model = body.get("model", "unknown")
        logger.info(f"Chat completion request | model={model}")

        # Проксируем к Ollama
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/v1/chat/completions",
                json=body,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            elapsed = time.time() - started_at
            logger.info(f"Chat completion success | model={model} | time={elapsed:.2f}s")

            return response.json()

    except httpx.TimeoutException:
        elapsed = time.time() - started_at
        logger.error(f"Ollama timeout after {elapsed:.1f}s")
        raise HTTPException(
            status_code=504,
            detail="Ollama timeout - запрос слишком долго обрабатывается",
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Ollama HTTP error: {e.response.status_code}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ollama error: {e.response.text}",
        )
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Не удалось подключиться к Ollama: {str(e)}",
        )
    except Exception as e:
        elapsed = time.time() - started_at
        logger.exception(f"Unexpected error after {elapsed:.1f}s")
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка proxy: {str(e)}",
        )


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_ollama_api(path: str, request: Request):
    """
    Проксирует все Ollama API endpoints (/api/*).

    Это позволяет использовать нативный Ollama API напрямую.
    """
    started_at = time.time()

    try:
        # Читаем body если есть
        body = None
        if request.method in ("POST", "PUT"):
            body = await request.body()

        logger.info(f"Ollama API request | {request.method} /api/{path}")

        # Проксируем к Ollama
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.request(
                method=request.method,
                url=f"{OLLAMA_BASE_URL}/api/{path}",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            elapsed = time.time() - started_at
            logger.info(f"Ollama API success | {request.method} /api/{path} | time={elapsed:.2f}s")

            return JSONResponse(
                content=response.json() if response.text else {},
                status_code=response.status_code,
            )

    except httpx.TimeoutException:
        elapsed = time.time() - started_at
        logger.error(f"Ollama API timeout after {elapsed:.1f}s | {request.method} /api/{path}")
        raise HTTPException(status_code=504, detail="Ollama timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"Ollama API HTTP error: {e.response.status_code} | {request.method} /api/{path}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ollama error: {e.response.text}",
        )
    except Exception as e:
        elapsed = time.time() - started_at
        logger.exception(f"Unexpected error after {elapsed:.1f}s | {request.method} /api/{path}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Ollama Proxy on port 8888")
    logger.info(f"Proxying to: {OLLAMA_BASE_URL}")

    uvicorn.run(app, host="0.0.0.0", port=8888, log_level="info")
