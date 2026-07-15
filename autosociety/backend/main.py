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
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("AutoSociety API starting up")
    init_db()
    init_metrics_db()
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
