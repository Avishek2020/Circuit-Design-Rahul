"""
FastAPI route handlers for ColdChain Guardian AI.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.agent.investigator import ColdChainInvestigator
from backend.agent.tools import (
    load_synthetic_data,
    tool_get_fleet_summary,
    tool_get_shipment_analysis,
    tool_list_problem_shipments,
)
from backend.api.schemas import (
    FleetSummarySchema,
    HealthSchema,
    InvestigateRequest,
    InvestigationReportSchema,
    ProblemShipmentSchema,
    ShipmentAnalysisSchema,
)

router = APIRouter()


# ── dependency: shared investigator instance ──────────────────────────────────

_investigator: ColdChainInvestigator | None = None


def get_investigator() -> ColdChainInvestigator:
    global _investigator
    if _investigator is None:
        force_mock = not bool(os.environ.get("ANTHROPIC_API_KEY", ""))
        _investigator = ColdChainInvestigator(force_mock=force_mock)
    return _investigator


def _db_available() -> bool:
    try:
        from backend.db.connection import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthSchema, tags=["System"])
def health() -> HealthSchema:
    has_key    = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    agent_mode = "live" if has_key else "mock"
    return HealthSchema(
        status       = "ok",
        agent_mode   = agent_mode,
        db_available = _db_available(),
    )


@router.post("/investigate", response_model=InvestigationReportSchema, tags=["Agent"])
def investigate(
    body:        InvestigateRequest,
    investigator: ColdChainInvestigator = Depends(get_investigator),
) -> InvestigationReportSchema:
    """
    Run an AI-powered investigation on a natural-language query.
    Returns a structured report with findings, SOP citations, and recommended actions.
    """
    report = investigator.investigate(body.query)
    return InvestigationReportSchema(**report.to_dict())


@router.get(
    "/shipments/{shipment_id}/analysis",
    response_model=ShipmentAnalysisSchema,
    tags=["Shipments"],
)
def get_shipment_analysis(shipment_id: str) -> ShipmentAnalysisSchema:
    """Full temporal analysis for a single shipment."""
    data   = load_synthetic_data()
    result = tool_get_shipment_analysis(shipment_id.upper(), data)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return ShipmentAnalysisSchema(**result)


@router.get("/fleet/summary", response_model=FleetSummarySchema, tags=["Fleet"])
def get_fleet_summary() -> FleetSummarySchema:
    """Fleet-wide statistics."""
    data = load_synthetic_data()
    return FleetSummarySchema(**tool_get_fleet_summary(data))


@router.get(
    "/fleet/problems",
    response_model=list[ProblemShipmentSchema],
    tags=["Fleet"],
)
def list_problem_shipments(
    limit:         int         = Query(default=10, ge=1, le=100),
    status_filter: str | None  = Query(default=None),
) -> list[ProblemShipmentSchema]:
    """List shipments with excursions or incidents."""
    data    = load_synthetic_data()
    results = tool_list_problem_shipments(data, limit=limit, status_filter=status_filter)
    return [ProblemShipmentSchema(**r) for r in results]
