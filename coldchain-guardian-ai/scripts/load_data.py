"""
Load all synthetic JSON data into PostgreSQL.

Usage:
  python scripts/load_data.py            # insert, skip existing rows
  python scripts/load_data.py --reset    # truncate tables first, then insert

Requires DATABASE_URL in .env or environment.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.db.connection import (
    create_tables, db_session, enable_pgvector, get_engine,
)
from backend.models.logistics import (
    DoorEvent, Incident, MaintenanceReport, Shipment,
    TemperatureReading, Truck, Warehouse,
)

SYNTHETIC_DIR = ROOT / "data" / "synthetic"


# ── date/datetime helpers ─────────────────────────────────────────────────────

def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _date(s: str | None) -> date | None:
    if not s:
        return None
    return date.fromisoformat(s)


# ── per-table loaders ─────────────────────────────────────────────────────────

def _load_warehouses(session) -> int:
    rows = json.loads((SYNTHETIC_DIR / "warehouses.json").read_text())
    for r in rows:
        stmt = pg_insert(Warehouse).values(
            warehouse_id              = r["warehouse_id"],
            name                      = r["name"],
            location                  = r["location"],
            latitude                  = r["latitude"],
            longitude                 = r["longitude"],
            capacity_pallets          = r["capacity_pallets"],
            current_occupancy_pallets = r["current_occupancy_pallets"],
            temperature_zones         = r["temperature_zones"],
            certifications            = r["certifications"],
            contact_manager           = r["contact_manager"],
            phone                     = r["phone"],
            operational_since         = _date(r["operational_since"]),
        ).on_conflict_do_nothing(index_elements=["warehouse_id"])
        session.execute(stmt)
    return len(rows)


def _load_trucks(session) -> int:
    rows = json.loads((SYNTHETIC_DIR / "trucks.json").read_text())
    for r in rows:
        stmt = pg_insert(Truck).values(
            truck_id              = r["truck_id"],
            license_plate         = r["license_plate"],
            make                  = r["make"],
            model                 = r["model"],
            year                  = r["year"],
            max_payload_kg        = r["max_payload_kg"],
            refrigeration_unit    = r["refrigeration_unit"],
            last_maintenance_date = _date(r["last_maintenance_date"]),
            next_maintenance_due  = _date(r["next_maintenance_due"]),
            current_status        = r["current_status"],
            assigned_driver       = r["assigned_driver"],
            notes                 = r.get("notes", ""),
        ).on_conflict_do_nothing(index_elements=["truck_id"])
        session.execute(stmt)
    return len(rows)


def _load_shipments(session) -> int:
    rows = json.loads((SYNTHETIC_DIR / "shipments.json").read_text())
    for r in rows:
        stmt = pg_insert(Shipment).values(
            shipment_id              = r["shipment_id"],
            origin_warehouse_id      = r["origin_warehouse_id"],
            destination_warehouse_id = r["destination_warehouse_id"],
            truck_id                 = r["truck_id"],
            product_type             = r["product_type"],
            product_category         = r["product_category"],
            required_temp_min        = r["required_temp_min"],
            required_temp_max        = r["required_temp_max"],
            quantity_kg              = r["quantity_kg"],
            departure_time           = _dt(r["departure_time"]),
            arrival_time             = _dt(r["arrival_time"]),
            status                   = r["status"],
            distance_km              = r["distance_km"],
            driver_name              = r["driver_name"],
            notes                    = r.get("notes", ""),
        ).on_conflict_do_nothing(index_elements=["shipment_id"])
        session.execute(stmt)
    return len(rows)


def _load_temperature_readings(session) -> int:
    rows = json.loads((SYNTHETIC_DIR / "temperature_readings.json").read_text())
    # Bulk insert in batches of 500
    batch_size = 500
    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        values = [
            dict(
                reading_id          = r["reading_id"],
                shipment_id         = r["shipment_id"],
                truck_id            = r["truck_id"],
                timestamp           = _dt(r["timestamp"]),
                temperature_celsius = r["temperature_celsius"],
                humidity_percent    = r["humidity_percent"],
                sensor_id           = r["sensor_id"],
                is_excursion        = r["is_excursion"],
                location_lat        = r["location_lat"],
                location_lon        = r["location_lon"],
            )
            for r in batch
        ]
        stmt = pg_insert(TemperatureReading).values(values).on_conflict_do_nothing(
            index_elements=["reading_id"]
        )
        session.execute(stmt)
        inserted += len(batch)
    return inserted


def _load_door_events(session) -> int:
    rows = json.loads((SYNTHETIC_DIR / "door_events.json").read_text())
    for r in rows:
        stmt = pg_insert(DoorEvent).values(
            event_id          = r["event_id"],
            shipment_id       = r["shipment_id"],
            truck_id          = r["truck_id"],
            timestamp         = _dt(r["timestamp"]),
            event_type        = r["event_type"],
            duration_seconds  = r.get("duration_seconds"),
            location_lat      = r["location_lat"],
            location_lon      = r["location_lon"],
            is_scheduled_stop = r["is_scheduled_stop"],
            notes             = r.get("notes", ""),
        ).on_conflict_do_nothing(index_elements=["event_id"])
        session.execute(stmt)
    return len(rows)


def _load_maintenance_reports(session) -> int:
    rows = json.loads((SYNTHETIC_DIR / "maintenance_reports.json").read_text())
    for r in rows:
        stmt = pg_insert(MaintenanceReport).values(
            report_id         = r["report_id"],
            truck_id          = r["truck_id"],
            date              = _date(r["date"]),
            type              = r["type"],
            description       = r["description"],
            technician        = r["technician"],
            cost_usd          = r["cost_usd"],
            issues_found      = r["issues_found"],
            parts_replaced    = r["parts_replaced"],
            next_service_km   = r["next_service_km"],
            passed_inspection = r["passed_inspection"],
        ).on_conflict_do_nothing(index_elements=["report_id"])
        session.execute(stmt)
    return len(rows)


def _load_incidents(session) -> int:
    rows = json.loads((SYNTHETIC_DIR / "incidents.json").read_text())
    for r in rows:
        stmt = pg_insert(Incident).values(
            incident_id           = r["incident_id"],
            shipment_id           = r["shipment_id"],
            truck_id              = r["truck_id"],
            warehouse_id          = r["warehouse_id"],
            type                  = r["type"],
            severity              = r["severity"],
            timestamp             = _dt(r["timestamp"]),
            duration_minutes      = r["duration_minutes"],
            max_temp_deviation    = r["max_temp_deviation"],
            description           = r["description"],
            regulatory_reportable = r["regulatory_reportable"],
            product_disposed      = r["product_disposed"],
            disposal_kg           = r["disposal_kg"],
            financial_loss_usd    = r["financial_loss_usd"],
            root_cause            = r["root_cause"],
            corrective_action     = r["corrective_action"],
            status                = r["status"],
            investigator          = r["investigator"],
        ).on_conflict_do_nothing(index_elements=["incident_id"])
        session.execute(stmt)
    return len(rows)


# ── main ──────────────────────────────────────────────────────────────────────

LOADERS = [
    ("warehouses",           Warehouse,           _load_warehouses),
    ("trucks",               Truck,               _load_trucks),
    ("shipments",            Shipment,            _load_shipments),
    ("temperature_readings", TemperatureReading,  _load_temperature_readings),
    ("door_events",          DoorEvent,           _load_door_events),
    ("maintenance_reports",  MaintenanceReport,   _load_maintenance_reports),
    ("incidents",            Incident,            _load_incidents),
]


def main(reset: bool = False) -> None:
    print("ColdChain Guardian AI – Data Loader")
    print("=" * 45)

    with db_session() as session:
        enable_pgvector(session)

    create_tables()

    if reset:
        print("  [reset] truncating logistics tables …")
        with db_session() as session:
            for name, model, _ in reversed(LOADERS):
                n = session.query(model).delete()
                print(f"    {name}: deleted {n} rows")

    print()
    total = 0
    for name, _, loader_fn in LOADERS:
        t0 = time.perf_counter()
        with db_session() as session:
            count = loader_fn(session)
        elapsed = time.perf_counter() - t0
        print(f"  {name:<25} {count:>5} rows  {elapsed:.2f}s")
        total += count

    print("=" * 45)
    print(f"  Total rows loaded: {total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Truncate tables before loading")
    args = parser.parse_args()
    main(reset=args.reset)
