"""
Unit tests for Day 4 temporal analysis — all pure-Python (no DB required).
"""

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── fixtures from synthetic JSON ─────────────────────────────────────────────

SYNTHETIC = ROOT / "data" / "synthetic"

def _load(name):
    return json.loads((SYNTHETIC / name).read_text())

def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ── MKT calculation ───────────────────────────────────────────────────────────

from backend.temporal.temperature import calculate_mkt, find_excursion_windows, analyze_temperature


def test_mkt_stable_temperature():
    """MKT of a constant temperature must equal that temperature."""
    readings = [{"temperature_celsius": -20.0, "timestamp": f"2024-01-01T{h:02d}:00:00Z"}
                for h in range(10)]
    mkt = calculate_mkt(readings)
    assert mkt is not None
    assert abs(mkt - (-20.0)) < 0.1


def test_mkt_requires_two_readings():
    assert calculate_mkt([]) is None
    assert calculate_mkt([{"temperature_celsius": 5.0, "timestamp": "2024-01-01T00:00:00Z"}]) is None


def test_mkt_higher_than_average_on_asymmetric_excursion():
    """MKT > arithmetic mean when there is a high-temperature excursion."""
    base   = [{"temperature_celsius": 2.0,  "timestamp": f"2024-01-01T0{i}:00:00Z"} for i in range(8)]
    hot    = [{"temperature_celsius": 25.0, "timestamp": f"2024-01-01T0{i}:30:00Z"} for i in range(2)]
    rdgs   = base + hot
    avg    = sum(r["temperature_celsius"] for r in rdgs) / len(rdgs)
    mkt    = calculate_mkt(rdgs)
    assert mkt is not None
    assert mkt > avg, f"MKT ({mkt:.2f}) should exceed mean ({avg:.2f}) for asymmetric excursion"


# ── excursion window detection ────────────────────────────────────────────────

def _make_readings(temps: list[float], t_min: float, t_max: float) -> list[dict]:
    base = datetime(2024, 10, 1, 6, 0, tzinfo=timezone.utc)
    return [
        {
            "temperature_celsius": t,
            "timestamp": (base + timedelta(minutes=15 * i)).isoformat(),
            "is_excursion": not (t_min <= t <= t_max),
        }
        for i, t in enumerate(temps)
    ]


def test_no_excursion_windows():
    rdgs = _make_readings([3.0, 3.5, 4.0, 2.5], 2.0, 8.0)
    assert find_excursion_windows(rdgs, 2.0, 8.0) == []


def test_single_excursion_window():
    temps = [3.0, 3.0, 12.0, 11.5, 13.0, 3.0, 3.0]
    rdgs  = _make_readings(temps, 2.0, 8.0)
    wins  = find_excursion_windows(rdgs, 2.0, 8.0)
    assert len(wins) == 1
    assert wins[0].direction == "above_max"
    assert wins[0].peak_temperature == 13.0
    assert wins[0].readings_in_window == 3


def test_two_separate_windows():
    temps = [3.0, 12.0, 3.0, 3.0, -5.0, 3.0]
    rdgs  = _make_readings(temps, 2.0, 8.0)
    wins  = find_excursion_windows(rdgs, 2.0, 8.0)
    assert len(wins) == 2
    assert wins[0].direction == "above_max"
    assert wins[1].direction == "below_min"


def test_window_duration():
    temps = [3.0, 12.0, 11.0, 10.0, 3.0]  # 3 excursion readings × 15 min apart = 30 min
    rdgs  = _make_readings(temps, 2.0, 8.0)
    wins  = find_excursion_windows(rdgs, 2.0, 8.0)
    assert len(wins) == 1
    assert wins[0].duration_minutes == 30.0


def test_window_severity():
    temps_minor    = [3.0, 9.0, 3.0]            # +1°C deviation — low
    temps_critical = [3.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 3.0]  # +12°C for 120 min
    rdgs_minor    = _make_readings(temps_minor,    2.0, 8.0)
    rdgs_critical = _make_readings(temps_critical, 2.0, 8.0)
    assert find_excursion_windows(rdgs_minor,    2.0, 8.0)[0].severity == "low"
    assert find_excursion_windows(rdgs_critical, 2.0, 8.0)[0].severity == "critical"


def test_analyze_temperature_full():
    shp = {
        "shipment_id": "SHP-TEST",
        "required_temp_min": 2.0,
        "required_temp_max": 8.0,
    }
    temps = [3.0, 3.5, 12.0, 11.0, 3.0, 3.0]
    rdgs  = _make_readings(temps, 2.0, 8.0)
    ta    = analyze_temperature(shp, rdgs)

    assert ta.shipment_id      == "SHP-TEST"
    assert ta.total_readings   == 6
    assert ta.excursion_count  == 2
    assert len(ta.excursion_windows) == 1
    assert ta.mkt_celsius is not None
    assert not ta.is_compliant


def test_analyze_temperature_empty_readings():
    shp = {"shipment_id": "SHP-EMPTY", "required_temp_min": -25, "required_temp_max": -15}
    ta  = analyze_temperature(shp, [])
    assert ta.total_readings == 0
    assert ta.is_compliant


# ── timeline builder ──────────────────────────────────────────────────────────

from backend.temporal.timeline import (
    build_timeline,
    EV_DEPARTURE, EV_ARRIVAL, EV_EXCURSION_START,
    EV_DOOR_OPEN_UNSCHEDULED,
)


def _make_shipment(sid="SHP-TEST", cat="frozen", tmin=-25.0, tmax=-15.0):
    return {
        "shipment_id":               sid,
        "truck_id":                  "TRK-001",
        "product_type":              "Frozen Beef",
        "product_category":          cat,
        "required_temp_min":         tmin,
        "required_temp_max":         tmax,
        "quantity_kg":               500,
        "departure_time":            "2024-10-01T06:00:00Z",
        "arrival_time":              "2024-10-01T14:00:00Z",
        "status":                    "failed_inspection",
        "origin_warehouse_id":       "WH-01",
        "destination_warehouse_id":  "WH-05",
        "driver_name":               "Test Driver",
    }


def test_timeline_always_has_departure_arrival():
    tl = build_timeline(_make_shipment(), [], [], [], [], [])
    types = {e.event_type for e in tl.events}
    assert EV_DEPARTURE in types
    assert EV_ARRIVAL   in types


def test_timeline_sorted():
    door = [{
        "event_id": "DOOR-001", "event_type": "open",
        "timestamp": "2024-10-01T10:00:00Z", "is_scheduled_stop": False,
        "location_lat": 41.0, "location_lon": -88.0, "notes": "night stop",
    }]
    tl = build_timeline(_make_shipment(), [], door, [], [], [])
    for i in range(len(tl.events) - 1):
        assert tl.events[i].timestamp <= tl.events[i + 1].timestamp


def test_timeline_excursion_events():
    temps = [-20.0, -20.0, -8.0, -8.0, -20.0]  # 2 excursion readings
    rdgs  = _make_readings(temps, -25.0, -15.0)
    shp   = _make_shipment()
    from backend.temporal.temperature import find_excursion_windows
    wins  = find_excursion_windows(rdgs, -25.0, -15.0)
    tl    = build_timeline(shp, rdgs, [], wins, [], [])
    exc_e = tl.excursion_events
    assert len(exc_e) > 0


def test_timeline_unscheduled_door_flagged():
    door = [{
        "event_id": "DOOR-001", "event_type": "open",
        "timestamp": "2024-10-01T03:00:00Z", "is_scheduled_stop": False,
        "location_lat": 41.0, "location_lon": -88.0, "notes": "Unscheduled overnight access",
    }]
    tl = build_timeline(_make_shipment(), [], door, [], [], [])
    assert any(e.event_type == EV_DOOR_OPEN_UNSCHEDULED for e in tl.events)


# ── correlation detection ─────────────────────────────────────────────────────

from backend.temporal.correlation import (
    find_door_excursion_correlations,
    find_maintenance_correlations,
    detect_fleet_patterns,
    detect_night_stop_pattern,
)
from backend.temporal.temperature import find_excursion_windows


def test_door_excursion_correlation_detected():
    shp   = _make_shipment()
    temps = [-20.0, -20.0, -8.0, -8.0, -20.0]
    rdgs  = _make_readings(temps, -25.0, -15.0)
    door  = [{
        "event_id": "DOOR-001", "event_type": "open",
        # 25 minutes before first excursion at index 2 (06:30)
        "timestamp": "2024-10-01T06:05:00Z",
        "is_scheduled_stop": False,
        "location_lat": 41.0, "location_lon": -88.0, "notes": "",
    }]
    wins = find_excursion_windows(rdgs, -25.0, -15.0)
    tl   = build_timeline(shp, rdgs, door, wins, [], [])
    findings = find_door_excursion_correlations(tl, wins)
    assert len(findings) >= 1
    assert findings[0].confidence >= 0.70


def test_no_door_correlation_without_preceding_door():
    shp   = _make_shipment()
    temps = [-20.0, -20.0, -8.0, -20.0]
    rdgs  = _make_readings(temps, -25.0, -15.0)
    wins  = find_excursion_windows(rdgs, -25.0, -15.0)
    tl    = build_timeline(shp, rdgs, [], wins, [], [])
    assert find_door_excursion_correlations(tl, wins) == []


def test_maintenance_correlation_failed_inspection():
    truck = {
        "truck_id": "TRK-001",
        "next_maintenance_due": "2025-12-01",
    }
    maint = [{
        "report_id": "MNT-001", "truck_id": "TRK-001",
        "date": "2024-08-01", "type": "scheduled",
        "passed_inspection": False,
        "issues_found": ["compressor_noise"],
        "parts_replaced": [], "technician": "Mike",
    }]
    incident_time = datetime(2024, 10, 1, tzinfo=timezone.utc)
    findings = find_maintenance_correlations(truck, maint, incident_time=incident_time)
    assert any(f.finding_type == "maintenance_failed_inspection" for f in findings)
    assert any(f.confidence >= 0.60 for f in findings)


def test_maintenance_correlation_overdue():
    truck = {
        "truck_id": "TRK-001",
        "next_maintenance_due": "2024-07-01",   # overdue by ~92 days on Oct 1
    }
    incident_time = datetime(2024, 10, 1, tzinfo=timezone.utc)
    findings = find_maintenance_correlations(truck, [], incident_time=incident_time)
    assert any(f.finding_type == "maintenance_overdue" for f in findings)


def test_fleet_pattern_recurring_truck():
    shipments = [{"shipment_id": "SHP-0001", "truck_id": "TRK-003"}]
    incidents = [
        {"incident_id": "INC-001", "truck_id": "TRK-003", "shipment_id": "SHP-0001"},
        {"incident_id": "INC-002", "truck_id": "TRK-003", "shipment_id": "SHP-0001"},
        {"incident_id": "INC-003", "truck_id": "TRK-003", "shipment_id": "SHP-0001"},
    ]
    patterns = detect_fleet_patterns(shipments, incidents, [])
    assert any(p.finding_type == "recurring_truck_incidents" for p in patterns)


def test_night_stop_flagged():
    shp  = _make_shipment()
    door = [{
        "event_id": "DOOR-001", "event_type": "open",
        "timestamp": "2024-10-01T03:15:00Z",   # 3:15 AM UTC
        "is_scheduled_stop": False,
        "location_lat": 41.0, "location_lon": -88.0, "notes": "night stop",
    }]
    tl = build_timeline(shp, [], door, [], [], [])
    finding = detect_night_stop_pattern(tl)
    assert finding is not None
    assert finding.finding_type == "night_stop_unscheduled_access"


def test_night_stop_not_flagged_scheduled():
    shp  = _make_shipment()
    door = [{
        "event_id": "DOOR-001", "event_type": "open",
        "timestamp": "2024-10-01T03:15:00Z",   # 3 AM but SCHEDULED
        "is_scheduled_stop": True,
        "location_lat": 41.0, "location_lon": -88.0, "notes": "",
    }]
    tl = build_timeline(shp, [], door, [], [], [])
    assert detect_night_stop_pattern(tl) is None


# ── full analysis pipeline on real synthetic data ─────────────────────────────

from backend.temporal.analysis import analyze_shipment_from_dicts


def test_full_analysis_problem_shipment():
    """End-to-end test on a shipment with real excursion data from the JSON files."""
    shipments = _load("shipments.json")
    readings  = _load("temperature_readings.json")
    doors     = _load("door_events.json")
    incidents = _load("incidents.json")
    maint     = _load("maintenance_reports.json")
    trucks    = _load("trucks.json")

    # Find the first shipment with excursion readings
    exc_sids = {r["shipment_id"] for r in readings if r["is_excursion"]}
    assert exc_sids, "Need at least one shipment with excursions"
    sid = sorted(exc_sids)[0]

    shp   = next(s for s in shipments if s["shipment_id"] == sid)
    rdgs  = [r for r in readings  if r["shipment_id"] == sid]
    devts = [d for d in doors     if d["shipment_id"] == sid]
    incs  = [i for i in incidents if i["shipment_id"] == sid]
    truck = next((t for t in trucks if t["truck_id"] == shp["truck_id"]), None)
    maint_t = [m for m in maint if m["truck_id"] == shp["truck_id"]]

    result = analyze_shipment_from_dicts(shp, rdgs, devts, incs, maint_t, truck)

    assert result.shipment_id == sid
    assert result.temperature.total_readings == len(rdgs)
    assert len(result.temperature.excursion_windows) > 0
    assert result.risk_score > 0
    assert result.timeline is not None
    assert len(result.timeline.events) >= 2  # at minimum departure + arrival

    # Evidence summary should contain key sections
    summary = result.to_evidence_summary()
    assert "SHIPMENT ANALYSIS" in summary
    assert "TEMPERATURE ANALYSIS" in summary
    assert "TIMELINE" in summary
    assert sid in summary


def test_evidence_summary_all_sections():
    """Ensure the evidence summary renders all major sections."""
    shipments = _load("shipments.json")
    readings  = _load("temperature_readings.json")
    doors     = _load("door_events.json")
    incidents = _load("incidents.json")
    maint     = _load("maintenance_reports.json")
    trucks    = _load("trucks.json")

    exc_sids = {r["shipment_id"] for r in readings if r["is_excursion"]}
    sid   = sorted(exc_sids)[0]
    shp   = next(s for s in shipments if s["shipment_id"] == sid)
    rdgs  = [r for r in readings  if r["shipment_id"] == sid]
    truck = next((t for t in trucks if t["truck_id"] == shp["truck_id"]), None)
    maint_t = [m for m in maint if m["truck_id"] == shp.get("truck_id")]

    result = analyze_shipment_from_dicts(shp, rdgs, [], [], maint_t, truck)
    summary = result.to_evidence_summary()

    for section in ["Risk Score", "TEMPERATURE ANALYSIS", "TIMELINE"]:
        assert section in summary, f"Missing section: {section!r}"
