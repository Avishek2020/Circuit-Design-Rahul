"""
Tests for Day 3 retrieval layer.

Pure-Python tests (entity extraction, context rendering) run always.
DB-backed tests are skipped when PostgreSQL is unavailable.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.conftest import requires_db


# ── entity extraction (no DB) ─────────────────────────────────────────────────

from backend.retrieval.sql_filter import extract_entity_ids


def test_extract_shipment_id():
    ids = extract_entity_ids("What happened with shipment SHP-0023?")
    assert ids.get("shipment") == ["SHP-0023"]


def test_extract_truck_id():
    ids = extract_entity_ids("Show maintenance history for TRK-007")
    assert "TRK-007" in ids.get("truck", [])


def test_extract_warehouse_id():
    ids = extract_entity_ids("Is WH-03 certified under HACCP?")
    assert "WH-03" in ids.get("warehouse", [])


def test_extract_multiple_entities():
    ids = extract_entity_ids("Was TRK-005 assigned to SHP-0042 when INC-003 occurred?")
    assert "TRK-005" in ids.get("truck", [])
    assert "SHP-0042" in ids.get("shipment", [])
    assert "INC-003" in ids.get("incident", [])


def test_extract_no_entities():
    ids = extract_entity_ids("What is the protocol for a temperature excursion?")
    assert ids == {}


def test_extract_case_insensitive():
    ids = extract_entity_ids("check shp-0001 and trk-002")
    assert "SHP-0001" in ids.get("shipment", [])
    assert "TRK-002" in ids.get("truck", [])


def test_extract_deduplicates():
    ids = extract_entity_ids("SHP-0001 was affected, as was SHP-0001 again")
    assert ids["shipment"].count("SHP-0001") == 1


# ── context string rendering (no DB) ─────────────────────────────────────────

from backend.retrieval.hybrid import RetrievalContext
from backend.retrieval.semantic import SemanticResult


def _make_context(**overrides) -> RetrievalContext:
    defaults = dict(
        query="test",
        entities={},
        semantic_results=[],
        shipments=[],
        trucks=[],
        warehouses=[],
        incidents=[],
        temperature_summaries=[],
        door_events=[],
        maintenance_reports=[],
    )
    defaults.update(overrides)
    return RetrievalContext(**defaults)


def test_empty_context_string():
    ctx = _make_context()
    s = ctx.to_context_string()
    assert "No relevant data" in s


def test_context_includes_sop_citation():
    r = SemanticResult(
        chunk_id="abc",
        sop_number="SOP-001",
        sop_title="Temperature Monitoring",
        section_title="4. Required Temperature Ranges by Product Category",
        page_start=2,
        text="Frozen goods must be maintained at -25°C to -15°C.",
        word_count=10,
        score=0.91,
        source_file="SOP-001_Temperature_Monitoring_Control.pdf",
    )
    ctx = _make_context(semantic_results=[r])
    s = ctx.to_context_string()
    assert "SOP-001" in s
    assert "relevance=0.91" in s
    assert "-25°C" in s


def test_context_includes_shipment():
    shp = {
        "shipment_id": "SHP-0023", "truck_id": "TRK-007",
        "product_type": "Frozen Beef", "status": "failed_inspection",
        "origin_warehouse_id": "WH-03", "destination_warehouse_id": "WH-07",
        "departure_time": "2024-10-15T06:00:00",
        "arrival_time":   "2024-10-15T14:00:00",
        "required_temp_min": -25, "required_temp_max": -15,
        "quantity_kg": 850, "driver_name": "Maria Gonzalez", "notes": "Excursion noted",
    }
    ctx = _make_context(shipments=[shp])
    s = ctx.to_context_string()
    assert "SHP-0023" in s
    assert "failed_inspection" in s


def test_context_flags_regulatory_incident():
    inc = {
        "incident_id": "INC-001", "shipment_id": "SHP-0023",
        "severity": "critical", "type": "temperature_excursion",
        "timestamp": "2024-10-15T03:45:00", "duration_minutes": 75,
        "max_temp_deviation": 6.2, "root_cause": "refrigeration_unit_failure",
        "product_disposed": True, "disposal_kg": 850, "financial_loss_usd": 12500,
        "corrective_action": "Emergency repair",
        "investigator": "Dr. Patricia Wells", "status": "closed",
        "regulatory_reportable": True,
    }
    ctx = _make_context(incidents=[inc])
    s = ctx.to_context_string()
    assert "REGULATORY REPORTABLE" in s
    assert "CRITICAL" in s
    assert "$12,500" in s


def test_context_flags_unscheduled_door_event():
    de = {
        "event_id": "DOOR-00001", "shipment_id": "SHP-0001",
        "truck_id": "TRK-007", "timestamp": "2024-10-06T02:42:31",
        "event_type": "open", "duration_seconds": None,
        "location_lat": 35.967, "location_lon": -90.303,
        "is_scheduled_stop": False, "notes": "Unscheduled overnight access",
    }
    ctx = _make_context(door_events=[de])
    s = ctx.to_context_string()
    assert "UNSCHEDULED" in s


def test_context_flags_temp_excursion():
    ts = {
        "shipment_id": "SHP-0023",
        "total_readings": 48, "excursion_count": 12,
        "min_temp": -22.1, "max_temp": -8.8, "avg_temp": -17.3,
        "first_excursion_at": "2024-10-15T03:30:00",
        "last_excursion_at":  "2024-10-15T05:00:00",
    }
    ctx = _make_context(temperature_summaries=[ts])
    s = ctx.to_context_string()
    assert "EXCURSIONS DETECTED" in s
    assert "12" in s


def test_maintenance_fail_flagged():
    mr = {
        "report_id": "MNT-005", "truck_id": "TRK-007",
        "date": "2024-06-01", "type": "unscheduled",
        "passed_inspection": False,
        "issues_found": ["compressor_noise"],
        "parts_replaced": ["compressor_belt"],
        "cost_usd": 2800, "technician": "Mike Torres",
    }
    ctx = _make_context(maintenance_reports=[mr])
    s = ctx.to_context_string()
    assert "FAIL" in s


# ── DB-backed tests ───────────────────────────────────────────────────────────

@requires_db
def test_fleet_summary_shape():
    from backend.retrieval.sql_filter import get_fleet_summary
    summary = get_fleet_summary()
    assert "total_shipments" in summary
    assert summary["total_shipments"] > 0


@requires_db
def test_get_shipment_known():
    from backend.retrieval.sql_filter import get_shipment
    shp = get_shipment("SHP-0001")
    assert shp is not None
    assert shp["shipment_id"] == "SHP-0001"


@requires_db
def test_get_shipment_unknown():
    from backend.retrieval.sql_filter import get_shipment
    assert get_shipment("SHP-9999") is None


@requires_db
def test_temperature_summary_exists():
    from backend.retrieval.sql_filter import get_temperature_summary
    ts = get_temperature_summary("SHP-0001")
    assert ts is not None
    assert ts["total_readings"] > 0


@requires_db
def test_problem_shipments():
    from backend.retrieval.sql_filter import get_problem_shipments
    probs = get_problem_shipments()
    assert len(probs) > 0
    for s in probs:
        assert s["status"] in ("failed_inspection", "delayed")


@requires_db
def test_hybrid_retrieve_shipment_query():
    from backend.retrieval.hybrid import HybridRetriever
    r = HybridRetriever()
    ctx = r.retrieve("What happened with shipment SHP-0001?")
    assert len(ctx.shipments) == 1
    assert ctx.shipments[0]["shipment_id"] == "SHP-0001"
    s = ctx.to_context_string()
    assert "SHP-0001" in s


@requires_db
def test_hybrid_retrieve_semantic_only():
    from backend.retrieval.hybrid import HybridRetriever
    r = HybridRetriever(semantic_top_k=3)
    ctx = r.retrieve("What is the required temperature range for frozen goods?")
    assert len(ctx.semantic_results) > 0
    assert len(ctx.entities) == 0
