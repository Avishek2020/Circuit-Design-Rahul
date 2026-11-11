"""
ColdChain Guardian AI — FastAPI application entry point.

Run with:
    uvicorn backend.api.main:app --reload --port 8000
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.api.routes import router

app = FastAPI(
    title       = "ColdChain Guardian AI",
    description = "AI-powered cold-chain logistics investigation and monitoring.",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],   # tighten for production
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root():
    return {"message": "ColdChain Guardian AI — visit /docs for API reference."}
