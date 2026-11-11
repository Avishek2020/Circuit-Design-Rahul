"""
Agent tool implementations and Anthropic tool schemas.

Tool functions accept pre-loaded dict data (no DB required) so they're
fully testable without PostgreSQL.  The investigator passes the loaded
data at construction time.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.temporal.analysis import analyze_shipment_from_dicts

# ── data loader ───────────────────────────────────────────────────────────────

_DATA_CACHE: dict[str, Any] | None = None

def load_synthetic_data(data_dir: Path | None = None) -> dict[str, list[dict]]:
    """Load all 7 synthetic JSON files into a single dict (cached)."""
    global _DATA_CACHE
    if _DATA_CACHE is not None:
        return _DATA_CACHE

    d = data_dir or ROOT / "data" / "synthetic"
    files = [
        "shipments", "trucks", "warehouses",
        "temperature_readings", "door_events",
        "maintenance_reports", "incidents",
    ]
    result: dict[str, list[dict]] = {}
    for name in files:
        p = d / f"{name}.json"
        result[name] = json.loads(p.read_text()) if p.exists() else []

    _DATA_CACHE = result
    return result


def _clear_cache() -> None:
    global _DATA_CACHE
    _DATA_CACHE = None


# ── tool implementations ──────────────────────────────────────────────────────

def tool_get_shipment_analysis(
    shipment_id: str,
    data: dict[str, list[dict]],
) -> dict:
    """Full temporal analysis for one shipment from pre-loaded dict data."""
    sid = shipment_id.upper().strip()

    shp = next((s for s in data["shipments"] if s["shipment_id"] == sid), None)
    if not shp:
        return {"error": f"Shipment {sid} not found."}

    rdgs   = [r for r in data["temperature_readings"] if r["shipment_id"] == sid]
    doors  = [d for d in data["door_events"]          if d["shipment_id"] == sid]
    incs   = [i for i in data["incidents"]             if i["shipment_id"] == sid]
    truck  = next((t for t in data["trucks"] if t["truck_id"] == shp.get("truck_id")), None)
    maint  = [m for m in data["maintenance_reports"] if m["truck_id"] == shp.get("truck_id")]

    result = analyze_shipment_from_dicts(shp, rdgs, doors, incs, maint, truck)
    return {
        "shipment_id":    sid,
        "risk_score":     result.risk_score,
        "risk_label":     result.risk_label,
        "evidence_summary": result.to_evidence_summary(),
        "excursion_windows": len(result.temperature.excursion_windows),
        "is_compliant":   result.temperature.is_compliant,
        "correlations":   [c.to_text() for c in result.correlations],
        "total_readings": result.temperature.total_readings,
        "mkt_celsius":    result.temperature.mkt_celsius,
    }


def tool_get_fleet_summary(data: dict[str, list[dict]]) -> dict:
    """Aggregate fleet-wide statistics from all shipments."""
    shipments  = data["shipments"]
    readings   = data["temperature_readings"]
    incidents  = data["incidents"]
    trucks     = data["trucks"]

    exc_sids   = {r["shipment_id"] for r in readings if r.get("is_excursion")}
    inc_sids   = {i["shipment_id"] for i in incidents}
    total_loss = sum(i.get("financial_loss_usd", 0) or 0 for i in incidents)
    reg_count  = sum(1 for i in incidents if i.get("regulatory_reportable"))

    status_counts: dict[str, int] = {}
    for s in shipments:
        st = s.get("status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1

    maint_overdue = [
        t["truck_id"] for t in trucks
        if t.get("current_status") == "maintenance_required"
    ]

    return {
        "total_shipments":        len(shipments),
        "shipments_with_excursion": len(exc_sids),
        "shipments_with_incidents": len(inc_sids),
        "total_incidents":        len(incidents),
        "total_financial_loss_usd": total_loss,
        "regulatory_reportable_incidents": reg_count,
        "status_breakdown":       status_counts,
        "trucks_maintenance_overdue": maint_overdue,
        "total_trucks":           len(trucks),
    }


def tool_list_problem_shipments(
    data: dict[str, list[dict]],
    limit: int = 10,
    status_filter: str | None = None,
) -> list[dict]:
    """List shipments with excursions or incidents, sorted by severity."""
    exc_sids  = {r["shipment_id"] for r in data["temperature_readings"] if r.get("is_excursion")}
    inc_sids  = {i["shipment_id"] for i in data["incidents"]}
    problem   = exc_sids | inc_sids

    results = []
    for s in data["shipments"]:
        sid = s["shipment_id"]
        if sid not in problem:
            continue
        if status_filter and s.get("status") != status_filter:
            continue
        exc_count = sum(1 for r in data["temperature_readings"]
                        if r["shipment_id"] == sid and r.get("is_excursion"))
        inc_count = sum(1 for i in data["incidents"] if i["shipment_id"] == sid)
        results.append({
            "shipment_id":    sid,
            "status":         s.get("status"),
            "product_type":   s.get("product_type"),
            "truck_id":       s.get("truck_id"),
            "excursion_readings": exc_count,
            "incident_count": inc_count,
        })

    results.sort(key=lambda r: (r["incident_count"], r["excursion_readings"]), reverse=True)
    return results[:limit]


def tool_search_sop_documents(
    query: str,
    retriever: Any = None,
) -> list[dict]:
    """
    Semantic search over SOP document chunks.
    Returns simplified results for the agent context.
    Falls back to empty list when DB / retriever is unavailable.
    """
    if retriever is None:
        return [{"note": "SOP search requires database connection (retriever not available)."}]

    try:
        from backend.retrieval.semantic import semantic_search
        raw = semantic_search(query, top_k=5, retriever=retriever)
        return [
            {
                "citation": r.citation,
                "content":  r.content[:400],
                "score":    round(r.score, 3),
            }
            for r in raw
        ]
    except Exception as e:
        return [{"note": f"SOP search error: {e}"}]


# ── Anthropic tool schemas ────────────────────────────────────────────────────

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_shipment_analysis",
        "description": (
            "Retrieve a full temporal analysis for a specific shipment ID. "
            "Returns temperature excursion windows, MKT, risk score, door-event "
            "correlations, maintenance findings, and a formatted evidence summary. "
            "Call this whenever a specific shipment ID is mentioned or relevant."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "shipment_id": {
                    "type": "string",
                    "description": "Shipment identifier, e.g. SHP-0023",
                }
            },
            "required": ["shipment_id"],
        },
    },
    {
        "name": "get_fleet_summary",
        "description": (
            "Get fleet-wide statistics: total shipments, excursion counts, incident "
            "counts, financial losses, trucks with overdue maintenance, and status "
            "breakdown. Use this for broad fleet health questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_problem_shipments",
        "description": (
            "List shipments that have temperature excursions or incidents, "
            "sorted by severity. Use this to find the worst shipments or when "
            "the user asks about problematic/non-compliant shipments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number to return (default 10)",
                },
                "status_filter": {
                    "type": "string",
                    "description": "Optional status filter, e.g. 'failed_inspection'",
                },
            },
        },
    },
    {
        "name": "search_sop_documents",
        "description": (
            "Search food-safety SOP documents for regulatory standards, procedures, "
            "and compliance requirements relevant to cold-chain incidents. "
            "Use this to cite SOP sections in your findings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language query, e.g. 'temperature excursion documentation requirements'",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "submit_investigation_report",
        "description": (
            "Submit your final structured investigation report. "
            "Call this ONCE when you have gathered all evidence and are ready to "
            "present your conclusions. This ends the investigation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "2-4 sentence executive summary of findings",
                },
                "findings": {
                    "type": "array",
                    "description": "Specific evidence-backed findings",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title":    {"type": "string"},
                            "detail":   {"type": "string"},
                            "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["title", "detail", "severity"],
                    },
                },
                "sop_citations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "SOP section references, e.g. 'SOP-003 §4.2 Temperature Logging'",
                },
                "recommended_actions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Prioritised corrective/preventive actions",
                },
                "risk_level": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                },
                "regulatory_reportable": {
                    "type": "boolean",
                    "description": "Whether this incident requires regulatory notification",
                },
            },
            "required": [
                "summary", "findings", "recommended_actions",
                "risk_level", "regulatory_reportable",
            ],
        },
    },
]
