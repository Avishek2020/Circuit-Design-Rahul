"""
SQLAlchemy ORM models for the six logistics tables.
Mirrors the synthetic data schema in data/synthetic/*.json.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Float,
    Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID

from backend.models.document import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    id                        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    warehouse_id              = Column(String(20),  nullable=False, unique=True, index=True)
    name                      = Column(String(255), nullable=False)
    location                  = Column(String(255))
    latitude                  = Column(Float)
    longitude                 = Column(Float)
    capacity_pallets          = Column(Integer)
    current_occupancy_pallets = Column(Integer)
    temperature_zones         = Column(JSON)          # [{zone, type, temp_range}, ...]
    certifications            = Column(JSON)          # ["HACCP", ...]
    contact_manager           = Column(String(255))
    phone                     = Column(String(50))
    operational_since         = Column(Date)
    created_at                = Column(DateTime(timezone=True), server_default=func.now())


class Truck(Base):
    __tablename__ = "trucks"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    truck_id              = Column(String(20),  nullable=False, unique=True, index=True)
    license_plate         = Column(String(20))
    make                  = Column(String(50))
    model                 = Column(String(100))
    year                  = Column(Integer)
    max_payload_kg        = Column(Integer)
    refrigeration_unit    = Column(String(255))
    last_maintenance_date = Column(Date)
    next_maintenance_due  = Column(Date)
    current_status        = Column(String(50),  index=True)
    assigned_driver       = Column(String(255))
    notes                 = Column(Text, default="")
    created_at            = Column(DateTime(timezone=True), server_default=func.now())


class Shipment(Base):
    __tablename__ = "shipments"

    id                       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id              = Column(String(20),  nullable=False, unique=True, index=True)
    origin_warehouse_id      = Column(String(20),  index=True)
    destination_warehouse_id = Column(String(20),  index=True)
    truck_id                 = Column(String(20),  index=True)
    product_type             = Column(String(255))
    product_category         = Column(String(50),  index=True)
    required_temp_min        = Column(Float)
    required_temp_max        = Column(Float)
    quantity_kg              = Column(Integer)
    departure_time           = Column(DateTime(timezone=True))
    arrival_time             = Column(DateTime(timezone=True))
    status                   = Column(String(50),  index=True)
    distance_km              = Column(Integer)
    driver_name              = Column(String(255))
    notes                    = Column(Text, default="")
    created_at               = Column(DateTime(timezone=True), server_default=func.now())


class TemperatureReading(Base):
    __tablename__ = "temperature_readings"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reading_id          = Column(String(20),  nullable=False, unique=True, index=True)
    shipment_id         = Column(String(20),  index=True)
    truck_id            = Column(String(20),  index=True)
    timestamp           = Column(DateTime(timezone=True), index=True)
    temperature_celsius = Column(Float)
    humidity_percent    = Column(Float)
    sensor_id           = Column(String(50))
    is_excursion        = Column(Boolean,     default=False, index=True)
    location_lat        = Column(Float)
    location_lon        = Column(Float)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())


class DoorEvent(Base):
    __tablename__ = "door_events"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id          = Column(String(20),  nullable=False, unique=True, index=True)
    shipment_id       = Column(String(20),  index=True)
    truck_id          = Column(String(20),  index=True)
    timestamp         = Column(DateTime(timezone=True), index=True)
    event_type        = Column(String(10))  # "open" | "close"
    duration_seconds  = Column(Integer,     nullable=True)
    location_lat      = Column(Float)
    location_lon      = Column(Float)
    is_scheduled_stop = Column(Boolean, default=True)
    notes             = Column(Text, default="")
    created_at        = Column(DateTime(timezone=True), server_default=func.now())


class MaintenanceReport(Base):
    __tablename__ = "maintenance_reports"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id        = Column(String(20),  nullable=False, unique=True, index=True)
    truck_id         = Column(String(20),  index=True)
    date             = Column(Date,        index=True)
    type             = Column(String(50))  # scheduled | unscheduled | breakdown
    description      = Column(Text)
    technician       = Column(String(255))
    cost_usd         = Column(Integer)
    issues_found     = Column(JSON)  # ["door_seal_wear", ...]
    parts_replaced   = Column(JSON)  # ["compressor_belt", ...]
    next_service_km  = Column(Integer)
    passed_inspection = Column(Boolean, default=True, index=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())


class Incident(Base):
    __tablename__ = "incidents"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id          = Column(String(20),  nullable=False, unique=True, index=True)
    shipment_id          = Column(String(20),  index=True)
    truck_id             = Column(String(20),  index=True)
    warehouse_id         = Column(String(20),  index=True)
    type                 = Column(String(100), index=True)
    severity             = Column(String(20),  index=True)
    timestamp            = Column(DateTime(timezone=True))
    duration_minutes     = Column(Integer)
    max_temp_deviation   = Column(Float)
    description          = Column(Text)
    regulatory_reportable = Column(Boolean, default=False)
    product_disposed     = Column(Boolean, default=False)
    disposal_kg          = Column(Integer, default=0)
    financial_loss_usd   = Column(Integer, default=0)
    root_cause           = Column(String(255))
    corrective_action    = Column(Text)
    status               = Column(String(50),  index=True)
    investigator         = Column(String(255))
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
