"""Pydantic request/response schemas for the FastAPI API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── requests ──────────────────────────────────────────────────────────────────

class InvestigateRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=2000,
                       description="Natural-language investigation question")


# ── responses ─────────────────────────────────────────────────────────────────

class FindingSchema(BaseModel):
    title:    str
    detail:   str
    severity: str
    evidence: list[str] = []


class InvestigationReportSchema(BaseModel):
    query:                 str
    summary:               str
    findings:              list[FindingSchema]
    sop_citations:         list[str]
    recommended_actions:   list[str]
    risk_level:            str
    regulatory_reportable: bool
    shipments_analyzed:    list[str]
    generated_at:          datetime


class ShipmentAnalysisSchema(BaseModel):
    shipment_id:       str
    risk_score:        float
    risk_label:        str
    excursion_windows: int
    is_compliant:      bool
    total_readings:    int
    mkt_celsius:       float | None
    correlations:      list[str]
    evidence_summary:  str


class FleetSummarySchema(BaseModel):
    total_shipments:              int
    shipments_with_excursion:     int
    shipments_with_incidents:     int
    total_incidents:              int
    total_financial_loss_usd:     float
    regulatory_reportable_incidents: int
    status_breakdown:             dict[str, int]
    trucks_maintenance_overdue:   list[str]
    total_trucks:                 int


class HealthSchema(BaseModel):
    status:     str
    agent_mode: str           # "live" | "mock"
    db_available: bool
    version:    str = "1.0.0"


class ProblemShipmentSchema(BaseModel):
    shipment_id:         str
    status:              str | None
    product_type:        str | None
    truck_id:            str | None
    excursion_readings:  int
    incident_count:      int
