"""
FastAPI application for AutoSociety.
Wires the engine, simulation control, and query routers together.
"""

# Load .env before any module reads os.getenv()
from dotenv import load_dotenv
load_dotenv()

import litellm
# Enable robust retry logic on all LLM completions (e.g., 429 RateLimitErrors)
litellm.num_retries = 5

import logging
import os
import sys
import httpx
from contextlib import asynccontextmanager

# On Windows, asyncio ProactorEventLoop raises noisy ConnectionResetError [WinError 10054]
# inside _ProactorBasePipeTransport._call_connection_lost() when clients close sockets abruptly.
# We patch _call_connection_lost to safely catch OSError during shutdown/close.
if sys.platform == "win32":
    import asyncio.proactor_events as _pe
    import socket as _socket

    def _safe_call_connection_lost(self, exc):
        if self._called_connection_lost:
            return
        try:
            self._protocol.connection_lost(exc)
        finally:
            if hasattr(self, "_sock") and self._sock is not None:
                try:
                    if hasattr(self._sock, "shutdown") and self._sock.fileno() != -1:
                        self._sock.shutdown(_socket.SHUT_RDWR)
                except OSError:
                    pass
                finally:
                    try:
                        self._sock.close()
                    except OSError:
                        pass
                    self._sock = None
            server = self._server
            if server is not None:
                server._detach(self)
                self._server = None
            self._called_connection_lost = True

    _pe._ProactorBasePipeTransport._call_connection_lost = _safe_call_connection_lost

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from autosociety.backend.core.engine import SimulationEngine
from autosociety.backend.core.database import init_db
from autosociety.backend.core.metrics import init_metrics_db
from autosociety.backend.routers import simulation as sim_router
from autosociety.backend.routers import queries as query_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Singleton engine
engine = SimulationEngine()


async def _check_ollama():
    """Verify Ollama is reachable at startup. Logs a warning if not."""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{base_url}/api/tags")
            r.raise_for_status()
            data = r.json()
            model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
            models = [m["name"] for m in data.get("models", [])]
            if model in models or any(model in m for m in models):
                logger.info("Ollama OK — %s available", model)
            else:
                logger.warning(
                    "Ollama running but model '%s' not found. "
                    "Run: ollama pull %s", model, model
                )
    except Exception as e:
        logger.warning(
            "Ollama not reachable at %s (%s). "
            "Start it with: ollama serve", base_url, e
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("AutoSociety API starting up")
    init_db()
    init_metrics_db()
    await _check_ollama()
    sim_router.set_engine(engine)
    yield
    # Shutdown
    if engine.is_running:
        engine.stop()
        logger.info("AutoSociety API shut down")


app = FastAPI(
    title="AutoSociety",
    description="Multi-agent society simulator API",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sim_router.router)
app.include_router(query_router.router)


@app.get("/")
async def root():
    return {
        "app": "AutoSociety",
        "version": "0.4.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "engine_running": engine.is_running}
