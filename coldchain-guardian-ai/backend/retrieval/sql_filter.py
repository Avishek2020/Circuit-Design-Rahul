"""
SQL-based structured retrieval for logistics entities.

All public functions return plain dicts (not ORM objects) so callers
don't need to manage session lifetimes.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import func, text

from backend.db.connection import db_session
from backend.models.logistics import (
    DoorEvent, Incident, MaintenanceReport, Shipment,
    TemperatureReading, Truck, Warehouse,
)


# ── entity ID extraction ──────────────────────────────────────────────────────

_PATTERNS: dict[str, re.Pattern] = {
    "shipment":   re.compile(r"\bSHP-\d{4}\b",  re.IGNORECASE),
    "truck":      re.compile(r"\bTRK-\d{3}\b",  re.IGNORECASE),
    "warehouse":  re.compile(r"\bWH-\d{2}\b",   re.IGNORECASE),
    "incident":   re.compile(r"\bINC-\d{3}\b",  re.IGNORECASE),
    "report":     re.compile(r"\bMNT-\d{3}\b",  re.IGNORECASE),
}


def extract_entity_ids(text: str) -> dict[str, list[str]]:
    """Return a dict of entity type → list of unique IDs found in *text*."""
    return {
        etype: list({m.upper() for m in pat.findall(text)})
        for etype, pat in _PATTERNS.items()
        if pat.search(text)
    }


def _row_to_dict(obj) -> dict:
    """Convert a SQLAlchemy ORM object to a plain dict."""
    result = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        result[col.name] = val
    return result


# ── single-entity lookups ─────────────────────────────────────────────────────

def get_shipment(shipment_id: str) -> dict | None:
    with db_session() as s:
        obj = s.query(Shipment).filter_by(shipment_id=shipment_id.upper()).first()
        return _row_to_dict(obj) if obj else None


def get_truck(truck_id: str) -> dict | None:
    with db_session() as s:
        obj = s.query(Truck).filter_by(truck_id=truck_id.upper()).first()
        return _row_to_dict(obj) if obj else None


def get_warehouse(warehouse_id: str) -> dict | None:
    with db_session() as s:
        obj = s.query(Warehouse).filter_by(warehouse_id=warehouse_id.upper()).first()
        return _row_to_dict(obj) if obj else None


def get_incident(incident_id: str) -> dict | None:
    with db_session() as s:
        obj = s.query(Incident).filter_by(incident_id=incident_id.upper()).first()
        return _row_to_dict(obj) if obj else None


# ── temperature data ──────────────────────────────────────────────────────────

def get_temperature_summary(shipment_id: str) -> dict | None:
    """
    Return aggregate temperature stats for a shipment — not raw readings.
    Returns None if the shipment has no readings.
    """
    sid = shipment_id.upper()
    with db_session() as s:
        row = s.execute(text("""
            SELECT
                shipment_id,
                COUNT(*)                                   AS total_readings,
                SUM(CASE WHEN is_excursion THEN 1 ELSE 0 END) AS excursion_count,
                MIN(temperature_celsius)                   AS min_temp,
                MAX(temperature_celsius)                   AS max_temp,
                AVG(temperature_celsius)                   AS avg_temp,
                MIN(CASE WHEN is_excursion THEN timestamp END) AS first_excursion_at,
                MAX(CASE WHEN is_excursion THEN timestamp END) AS last_excursion_at
            FROM temperature_readings
            WHERE shipment_id = :sid
            GROUP BY shipment_id
        """), {"sid": sid}).fetchone()

    if not row or row.total_readings == 0:
        return None

    return {
        "shipment_id":       sid,
        "total_readings":    int(row.total_readings),
        "excursion_count":   int(row.excursion_count),
        "min_temp":          round(float(row.min_temp), 2),
        "max_temp":          round(float(row.max_temp), 2),
        "avg_temp":          round(float(row.avg_temp), 2),
        "first_excursion_at": row.first_excursion_at.isoformat() if row.first_excursion_at else None,
        "last_excursion_at":  row.last_excursion_at.isoformat()  if row.last_excursion_at  else None,
    }


def get_excursion_readings(shipment_id: str, limit: int = 20) -> list[dict]:
    """Return the actual excursion-flagged readings (capped at *limit*)."""
    sid = shipment_id.upper()
    with db_session() as s:
        objs = (
            s.query(TemperatureReading)
            .filter_by(shipment_id=sid, is_excursion=True)
            .order_by(TemperatureReading.timestamp)
            .limit(limit)
            .all()
        )
        return [_row_to_dict(o) for o in objs]


# ── door events ───────────────────────────────────────────────────────────────

def get_door_events(shipment_id: str) -> list[dict]:
    """Return all door events for a shipment, ordered by time."""
    sid = shipment_id.upper()
    with db_session() as s:
        objs = (
            s.query(DoorEvent)
            .filter_by(shipment_id=sid)
            .order_by(DoorEvent.timestamp)
            .all()
        )
        return [_row_to_dict(o) for o in objs]


def get_suspicious_door_events(shipment_id: str | None = None) -> list[dict]:
    """Return unscheduled door events (possible tampering)."""
    with db_session() as s:
        q = s.query(DoorEvent).filter_by(is_scheduled_stop=False, event_type="open")
        if shipment_id:
            q = q.filter_by(shipment_id=shipment_id.upper())
        objs = q.order_by(DoorEvent.timestamp).all()
        return [_row_to_dict(o) for o in objs]


# ── maintenance ───────────────────────────────────────────────────────────────

def get_maintenance_history(truck_id: str) -> list[dict]:
    """Return all maintenance reports for a truck, newest first."""
    tid = truck_id.upper()
    with db_session() as s:
        objs = (
            s.query(MaintenanceReport)
            .filter_by(truck_id=tid)
            .order_by(MaintenanceReport.date.desc())
            .all()
        )
        return [_row_to_dict(o) for o in objs]


def get_failed_inspections(truck_id: str | None = None) -> list[dict]:
    with db_session() as s:
        q = s.query(MaintenanceReport).filter_by(passed_inspection=False)
        if truck_id:
            q = q.filter_by(truck_id=truck_id.upper())
        return [_row_to_dict(o) for o in q.order_by(MaintenanceReport.date.desc()).all()]


# ── incidents ─────────────────────────────────────────────────────────────────

def get_incidents_for_shipment(shipment_id: str) -> list[dict]:
    sid = shipment_id.upper()
    with db_session() as s:
        objs = s.query(Incident).filter_by(shipment_id=sid).all()
        return [_row_to_dict(o) for o in objs]


def get_incidents_for_truck(truck_id: str) -> list[dict]:
    tid = truck_id.upper()
    with db_session() as s:
        objs = (
            s.query(Incident)
            .filter_by(truck_id=tid)
            .order_by(Incident.timestamp.desc())
            .all()
        )
        return [_row_to_dict(o) for o in objs]


def get_high_severity_incidents(limit: int = 10) -> list[dict]:
    with db_session() as s:
        objs = (
            s.query(Incident)
            .filter(Incident.severity.in_(["high", "critical"]))
            .order_by(Incident.financial_loss_usd.desc())
            .limit(limit)
            .all()
        )
        return [_row_to_dict(o) for o in objs]


# ── cross-entity analytics ────────────────────────────────────────────────────

def get_shipment_full_context(shipment_id: str) -> dict[str, Any]:
    """
    One-shot fetch of everything related to a shipment:
    shipment record, truck, origin/dest warehouses, temp summary,
    door events, incidents, maintenance history.
    """
    sid = shipment_id.upper()
    shp = get_shipment(sid)
    if not shp:
        return {"error": f"Shipment {sid} not found"}

    truck    = get_truck(shp["truck_id"])              if shp.get("truck_id")                 else None
    origin   = get_warehouse(shp["origin_warehouse_id"])      if shp.get("origin_warehouse_id")      else None
    dest     = get_warehouse(shp["destination_warehouse_id"]) if shp.get("destination_warehouse_id") else None
    temp_sum = get_temperature_summary(sid)
    doors    = get_door_events(sid)
    exc_rdgs = get_excursion_readings(sid) if (temp_sum and temp_sum["excursion_count"] > 0) else []
    incidents = get_incidents_for_shipment(sid)
    maint    = get_maintenance_history(shp["truck_id"]) if shp.get("truck_id") else []

    return {
        "shipment":              shp,
        "truck":                 truck,
        "origin_warehouse":      origin,
        "destination_warehouse": dest,
        "temperature_summary":   temp_sum,
        "excursion_readings":    exc_rdgs,
        "door_events":           doors,
        "incidents":             incidents,
        "maintenance_history":   maint,
    }


def get_problem_shipments(limit: int = 15) -> list[dict]:
    """Return shipments with failed_inspection or delayed status."""
    with db_session() as s:
        objs = (
            s.query(Shipment)
            .filter(Shipment.status.in_(["failed_inspection", "delayed"]))
            .order_by(Shipment.departure_time.desc())
            .limit(limit)
            .all()
        )
        return [_row_to_dict(o) for o in objs]


def get_fleet_summary() -> dict:
    """Return high-level fleet statistics."""
    with db_session() as s:
        total_shipments    = s.query(func.count(Shipment.id)).scalar()
        problem_shipments  = s.query(func.count(Shipment.id)).filter(
            Shipment.status.in_(["failed_inspection", "delayed"])
        ).scalar()
        total_excursions   = s.query(func.count(TemperatureReading.id)).filter_by(is_excursion=True).scalar()
        total_incidents    = s.query(func.count(Incident.id)).scalar()
        total_loss         = s.query(func.sum(Incident.financial_loss_usd)).scalar() or 0
        maint_failed       = s.query(func.count(MaintenanceReport.id)).filter_by(passed_inspection=False).scalar()
        suspicious_doors   = s.query(func.count(DoorEvent.id)).filter_by(
            is_scheduled_stop=False, event_type="open"
        ).scalar()

    return {
        "total_shipments":   total_shipments,
        "problem_shipments": problem_shipments,
        "total_excursions":  total_excursions,
        "total_incidents":   total_incidents,
        "total_financial_loss_usd": int(total_loss),
        "failed_inspections":       maint_failed,
        "suspicious_door_events":   suspicious_doors,
    }
