"""
Top-level temporal analysis orchestrator.

`analyze_shipment(shipment_id)` is the main entry point for the Day 5 AI agent.
It queries the DB, runs all temporal analyses, and returns a ShipmentAnalysis
with a formatted evidence summary.

Also provides `analyze_fleet()` for fleet-wide pattern reporting.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.temporal.correlation import (
    CorrelationFinding,
    detect_fleet_patterns,
    detect_night_stop_pattern,
    find_door_excursion_correlations,
    find_maintenance_correlations,
)
from backend.temporal.temperature import TemperatureAnalysis, analyze_temperature
from backend.temporal.timeline import ShipmentTimeline, build_timeline


# ── data class ────────────────────────────────────────────────────────────────

@dataclass
class ShipmentAnalysis:
    shipment_id:         str
    shipment:            dict
    truck:               dict | None
    timeline:            ShipmentTimeline
    temperature:         TemperatureAnalysis
    correlations:        list[CorrelationFinding]
    risk_score:          float          # 0–10

    @property
    def risk_label(self) -> str:
        if self.risk_score >= 8:
            return "CRITICAL"
        if self.risk_score >= 6:
            return "HIGH"
        if self.risk_score >= 4:
            return "MEDIUM"
        return "LOW"

    def to_evidence_summary(self) -> str:
        """
        Formatted evidence string for the AI investigation agent.
        Includes timeline, temperature analysis, and correlation findings.
        """
        shp = self.shipment
        lines = [
            f"=== SHIPMENT ANALYSIS: {self.shipment_id} ===",
            f"Risk Score: {self.risk_score:.1f}/10 ({self.risk_label})",
            f"Product:    {shp.get('product_type')} ({shp.get('product_category')})"
            f" | {shp.get('quantity_kg')} kg",
            f"Route:      {shp.get('origin_warehouse_id')} → {shp.get('destination_warehouse_id')}",
            f"Status:     {shp.get('status')}",
        ]
        if self.truck:
            t = self.truck
            lines.append(
                f"Truck:      {t.get('truck_id')} | {t.get('make')} {t.get('model')} {t.get('year')}"
                f" | Driver: {shp.get('driver_name')}"
            )

        lines += ["", "--- TEMPERATURE ANALYSIS ---"]
        lines += self.temperature.evidence_lines()

        lines += ["", "--- TIMELINE (KEY EVENTS) ---"]
        lines.append(self.timeline.to_text(max_events=25))

        if self.correlations:
            lines += ["", "--- CORRELATION FINDINGS ---"]
            for i, cf in enumerate(self.correlations, 1):
                lines.append(f"\n{i}. {cf.to_text()}")

        return "\n".join(lines)


@dataclass
class FleetAnalysis:
    generated_at:      datetime
    total_shipments:   int
    problem_shipments: list[dict]
    high_risk_trucks:  list[dict]
    fleet_patterns:    list[CorrelationFinding]
    top_incidents:     list[dict]
    summary_stats:     dict

    def to_summary_string(self) -> str:
        lines = [
            f"=== FLEET ANALYSIS (as of {self.generated_at.strftime('%Y-%m-%d')}) ===",
            f"Total shipments:   {self.total_shipments}",
            f"Problem shipments: {len(self.problem_shipments)}",
            f"High-risk trucks:  {len(self.high_risk_trucks)}",
        ]
        for k, v in self.summary_stats.items():
            lines.append(f"  {k}: {v}")
        if self.fleet_patterns:
            lines += ["", "Fleet-wide patterns:"]
            for p in self.fleet_patterns:
                lines.append(f"  · {p.description}")
        return "\n".join(lines)


# ── risk scoring ──────────────────────────────────────────────────────────────

def _risk_score(
    temp:         TemperatureAnalysis,
    correlations: list[CorrelationFinding],
    shipment:     dict,
) -> float:
    score = 0.0

    # Base from temperature excursions
    if temp.excursion_windows:
        worst = temp.worst_window
        score += min(4.0, len(temp.excursion_windows) * 1.5)
        score += min(3.0, abs(worst.max_deviation) * 0.4)
        score += min(1.5, worst.duration_minutes / 60)

    # From correlations
    for cf in correlations:
        if cf.severity == "critical":
            score += 1.5 * cf.confidence
        elif cf.severity == "high":
            score += 1.0 * cf.confidence
        else:
            score += 0.5 * cf.confidence

    # Failed status
    if shipment.get("status") in ("failed_inspection", "delayed"):
        score += 1.0

    # Pharma products are higher risk
    if shipment.get("product_category") == "pharma":
        score *= 1.2

    return round(min(score, 10.0), 1)


# ── from-dict analysis (no DB) ────────────────────────────────────────────────

def analyze_shipment_from_dicts(
    shipment:    dict,
    readings:    Sequence[dict],
    door_events: Sequence[dict],
    incidents:   Sequence[dict],
    maintenance: Sequence[dict],
    truck:       dict | None = None,
) -> ShipmentAnalysis:
    """
    Full analysis from pre-loaded dict data — no DB queries.
    Useful for testing and for passing context from hybrid retriever.
    """
    temp    = analyze_temperature(shipment, readings)
    windows = temp.excursion_windows

    timeline = build_timeline(
        shipment          = shipment,
        readings          = readings,
        door_events       = door_events,
        excursion_windows = windows,
        incidents         = incidents,
        maintenance       = maintenance,
    )

    correlations: list[CorrelationFinding] = []
    correlations.extend(find_door_excursion_correlations(timeline, windows))

    if truck:
        correlations.extend(
            find_maintenance_correlations(
                truck         = truck,
                maintenance   = maintenance,
                incident_time = timeline.departure_time,
            )
        )

    night = detect_night_stop_pattern(timeline)
    if night:
        correlations.append(night)

    score = _risk_score(temp, correlations, shipment)

    return ShipmentAnalysis(
        shipment_id  = shipment["shipment_id"],
        shipment     = shipment,
        truck        = truck,
        timeline     = timeline,
        temperature  = temp,
        correlations = correlations,
        risk_score   = score,
    )


# ── DB-backed entry points ────────────────────────────────────────────────────

def analyze_shipment(shipment_id: str) -> ShipmentAnalysis:
    """Fetch data from PostgreSQL and run full temporal analysis."""
    from backend.retrieval.sql_filter import (
        get_door_events,
        get_incidents_for_shipment,
        get_maintenance_history,
        get_shipment,
        get_temperature_summary,
        get_truck,
    )
    from backend.db.connection import db_session
    from backend.models.logistics import TemperatureReading

    sid = shipment_id.upper()
    shp = get_shipment(sid)
    if not shp:
        raise ValueError(f"Shipment {sid} not found in database.")

    truck     = get_truck(shp["truck_id"]) if shp.get("truck_id") else None
    doors     = get_door_events(sid)
    incidents = get_incidents_for_shipment(sid)
    maint     = get_maintenance_history(shp["truck_id"]) if shp.get("truck_id") else []

    # Fetch raw temperature readings (not just the summary)
    with db_session() as s:
        objs = (
            s.query(TemperatureReading)
            .filter_by(shipment_id=sid)
            .order_by(TemperatureReading.timestamp)
            .all()
        )
        readings = []
        for o in objs:
            readings.append({
                "reading_id":          o.reading_id,
                "shipment_id":         o.shipment_id,
                "timestamp":           o.timestamp.isoformat(),
                "temperature_celsius": o.temperature_celsius,
                "humidity_percent":    o.humidity_percent,
                "is_excursion":        o.is_excursion,
                "location_lat":        o.location_lat,
                "location_lon":        o.location_lon,
            })

    return analyze_shipment_from_dicts(shp, readings, doors, incidents, maint, truck)


def analyze_fleet() -> FleetAnalysis:
    """High-level fleet-wide pattern analysis (requires DB)."""
    from backend.retrieval.sql_filter import (
        get_fleet_summary,
        get_high_severity_incidents,
        get_problem_shipments,
    )
    from backend.db.connection import db_session
    from backend.models.logistics import Incident, Shipment, Truck
    import json

    with db_session() as s:
        all_shps  = [
            {c.name: getattr(o, c.name) for c in Shipment.__table__.columns}
            for o in s.query(Shipment).all()
        ]
        all_incs  = [
            {c.name: getattr(o, c.name) for c in Incident.__table__.columns}
            for o in s.query(Incident).all()
        ]
        all_trucks = [
            {c.name: getattr(o, c.name) for c in Truck.__table__.columns}
            for o in s.query(Truck).all()
        ]

    # Stringify datetimes
    for rec in all_shps + all_incs + all_trucks:
        for k, v in rec.items():
            if isinstance(v, datetime):
                rec[k] = v.isoformat()

    patterns       = detect_fleet_patterns(all_shps, all_incs, [])
    problem_shps   = get_problem_shipments(limit=20)
    top_incidents  = get_high_severity_incidents(limit=10)
    stats          = get_fleet_summary()

    # Identify high-risk trucks (multiple incidents or maintenance overdue)
    high_risk = [
        t for t in all_trucks
        if t.get("current_status") == "maintenance_required"
        or (t.get("notes") or "").lower().find("overdue") >= 0
    ]

    return FleetAnalysis(
        generated_at      = datetime.now(timezone.utc),
        total_shipments   = stats.get("total_shipments", 0),
        problem_shipments = problem_shps,
        high_risk_trucks  = high_risk,
        fleet_patterns    = patterns,
        top_incidents     = top_incidents,
        summary_stats     = stats,
    )
