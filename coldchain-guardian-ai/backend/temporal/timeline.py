"""
Chronological event timeline for a shipment transit.

Merges sensor readings, door events, maintenance records and incidents
into a single ordered sequence of TimelineEvent objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Sequence

from backend.temporal.temperature import ExcursionWindow, _parse_ts


# ── severity levels ───────────────────────────────────────────────────────────

SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class TimelineEvent:
    timestamp:   datetime
    event_type:  str    # see EVENT_TYPE constants below
    severity:    str    # "info" | "warning" | "high" | "critical"
    source:      str    # "sensor" | "door" | "maintenance" | "incident"
    title:       str
    detail:      str
    metadata:    dict   = field(default_factory=dict)

    # ── convenience ───────────────────────────────────────────────────────────

    @property
    def ts_label(self) -> str:
        return self.timestamp.strftime("%Y-%m-%dT%H:%MZ")

    @property
    def icon(self) -> str:
        return {
            "info":     "·",
            "warning":  "⚠",
            "high":     "🔴",
            "critical": "🚨",
        }.get(self.severity, "·")

    def one_line(self) -> str:
        return f"{self.ts_label}  {self.icon} [{self.event_type:<28}] {self.title}"


# ── event type constants ──────────────────────────────────────────────────────

EV_DEPARTURE             = "DEPARTURE"
EV_ARRIVAL               = "ARRIVAL"
EV_DOOR_OPEN             = "DOOR_OPEN"
EV_DOOR_OPEN_UNSCHEDULED = "DOOR_OPEN_UNSCHEDULED"
EV_DOOR_CLOSE            = "DOOR_CLOSE"
EV_EXCURSION_START       = "EXCURSION_START"
EV_EXCURSION_PEAK        = "EXCURSION_PEAK"
EV_EXCURSION_END         = "EXCURSION_END"
EV_MAINTENANCE_PASS      = "MAINTENANCE_PASS"
EV_MAINTENANCE_FAIL      = "MAINTENANCE_FAIL"
EV_INCIDENT              = "INCIDENT"


# ── dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class ShipmentTimeline:
    shipment_id:    str
    truck_id:       str
    departure_time: datetime
    arrival_time:   datetime
    events:         list[TimelineEvent]   # sorted ascending

    @property
    def duration_hours(self) -> float:
        return (self.arrival_time - self.departure_time).total_seconds() / 3600

    @property
    def excursion_events(self) -> list[TimelineEvent]:
        return [e for e in self.events if "EXCURSION" in e.event_type]

    @property
    def unscheduled_door_events(self) -> list[TimelineEvent]:
        return [e for e in self.events if e.event_type == EV_DOOR_OPEN_UNSCHEDULED]

    @property
    def has_incidents(self) -> bool:
        return any(e.event_type == EV_INCIDENT for e in self.events)

    def events_in_window(
        self,
        start: datetime,
        end: datetime,
    ) -> list[TimelineEvent]:
        return [e for e in self.events if start <= e.timestamp <= end]

    def to_text(self, max_events: int = 50) -> str:
        lines = [
            f"Timeline for {self.shipment_id} | {self.truck_id}",
            f"Duration: {self.departure_time.strftime('%Y-%m-%dT%H:%MZ')} – "
            f"{self.arrival_time.strftime('%Y-%m-%dT%H:%MZ')} "
            f"({self.duration_hours:.1f} h)",
            "─" * 70,
        ]
        shown = self.events[:max_events]
        for e in shown:
            lines.append(e.one_line())
            if e.detail:
                lines.append(f"    {e.detail}")
        if len(self.events) > max_events:
            lines.append(f"  … {len(self.events) - max_events} more events …")
        return "\n".join(lines)


# ── builder ───────────────────────────────────────────────────────────────────

def build_timeline(
    shipment:          dict,
    readings:          Sequence[dict],
    door_events:       Sequence[dict],
    excursion_windows: list[ExcursionWindow],
    incidents:         Sequence[dict],
    maintenance:       Sequence[dict],
) -> ShipmentTimeline:
    """
    Merge all event sources into a single chronological timeline.
    All inputs are plain dicts — no DB queries here.
    """
    events: list[TimelineEvent] = []

    dep = _parse_ts(shipment["departure_time"])
    arr = _parse_ts(shipment["arrival_time"])

    # ── Departure / Arrival ───────────────────────────────────────────────────
    events.append(TimelineEvent(
        timestamp  = dep,
        event_type = EV_DEPARTURE,
        severity   = "info",
        source     = "shipment",
        title      = f"Departed {shipment.get('origin_warehouse_id', '?')} → "
                     f"{shipment.get('destination_warehouse_id', '?')}",
        detail     = f"Product: {shipment.get('product_type', '?')} | "
                     f"{shipment.get('quantity_kg', '?')} kg | "
                     f"Driver: {shipment.get('driver_name', '?')}",
    ))
    events.append(TimelineEvent(
        timestamp  = arr,
        event_type = EV_ARRIVAL,
        severity   = "info",
        source     = "shipment",
        title      = f"Arrived {shipment.get('destination_warehouse_id', '?')}",
        detail     = f"Status: {shipment.get('status', '?')}",
    ))

    # ── Door events ───────────────────────────────────────────────────────────
    for de in door_events:
        ts        = _parse_ts(de["timestamp"])
        is_open   = de["event_type"] == "open"
        scheduled = de.get("is_scheduled_stop", True)
        note      = de.get("notes", "")

        if is_open:
            etype    = EV_DOOR_OPEN if scheduled else EV_DOOR_OPEN_UNSCHEDULED
            severity = "info" if scheduled else "warning"
            title    = "Door opened" + ("" if scheduled else " (UNSCHEDULED)")
        else:
            etype    = EV_DOOR_CLOSE
            severity = "info"
            dur      = de.get("duration_seconds")
            title    = "Door closed" + (f" ({dur}s open)" if dur else "")

        events.append(TimelineEvent(
            timestamp  = ts,
            event_type = etype,
            severity   = severity,
            source     = "door",
            title      = title,
            detail     = note or "",
            metadata   = {"event_id": de.get("event_id")},
        ))

    # ── Excursion windows ─────────────────────────────────────────────────────
    for w in excursion_windows:
        events.append(TimelineEvent(
            timestamp  = w.start_time,
            event_type = EV_EXCURSION_START,
            severity   = w.severity,
            source     = "sensor",
            title      = f"Temperature excursion starts: {w.start_time.strftime('%H:%MZ')}",
            detail     = f"First out-of-range reading: "
                         f"{'above max' if w.direction != 'below_min' else 'below min'} "
                         f"(deviation {'+' if w.max_deviation > 0 else ''}{w.max_deviation:.1f}°C)",
            metadata   = {"window_index": w.index},
        ))
        events.append(TimelineEvent(
            timestamp  = w.peak_time,
            event_type = EV_EXCURSION_PEAK,
            severity   = w.severity,
            source     = "sensor",
            title      = f"Peak: {w.peak_temperature:.1f}°C "
                         f"({'+' if w.max_deviation > 0 else ''}{w.max_deviation:.1f}°C vs limit)",
            detail     = w.summary(),
            metadata   = {"window_index": w.index},
        ))
        events.append(TimelineEvent(
            timestamp  = w.end_time,
            event_type = EV_EXCURSION_END,
            severity   = "warning",
            source     = "sensor",
            title      = f"Temperature excursion ends (duration: {w.duration_minutes:.0f} min)",
            detail     = "",
            metadata   = {"window_index": w.index},
        ))

    # ── Maintenance records (pre-transit context) ─────────────────────────────
    for mr in maintenance:
        date_str = mr.get("date", "")
        try:
            mr_dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        passed   = mr.get("passed_inspection", True)
        issues   = ", ".join(mr.get("issues_found") or []) or "none"
        events.append(TimelineEvent(
            timestamp  = mr_dt,
            event_type = EV_MAINTENANCE_FAIL if not passed else EV_MAINTENANCE_PASS,
            severity   = "high" if not passed else "info",
            source     = "maintenance",
            title      = f"Maintenance {mr.get('type', '?')}: "
                         f"{'FAILED' if not passed else 'passed'} inspection",
            detail     = f"Issues: {issues} | "
                         f"Parts: {', '.join(mr.get('parts_replaced') or []) or 'none'} | "
                         f"Tech: {mr.get('technician', '?')}",
            metadata   = {"report_id": mr.get("report_id")},
        ))

    # ── Incidents ─────────────────────────────────────────────────────────────
    for inc in incidents:
        ts       = _parse_ts(inc["timestamp"])
        severity = inc.get("severity", "medium")
        flag     = " ⚠ REGULATORY" if inc.get("regulatory_reportable") else ""
        events.append(TimelineEvent(
            timestamp  = ts,
            event_type = EV_INCIDENT,
            severity   = "critical" if severity in ("critical", "high") else "warning",
            source     = "incident",
            title      = f"Incident {inc.get('incident_id', '?')} — "
                         f"{inc.get('type', '?').replace('_', ' ')} "
                         f"[{severity.upper()}]{flag}",
            detail     = f"Root cause: {inc.get('root_cause', '?')} | "
                         f"Loss: ${inc.get('financial_loss_usd', 0):,}",
            metadata   = {"incident_id": inc.get("incident_id")},
        ))

    events.sort(key=lambda e: e.timestamp)

    return ShipmentTimeline(
        shipment_id    = shipment["shipment_id"],
        truck_id       = shipment.get("truck_id", ""),
        departure_time = dep,
        arrival_time   = arr,
        events         = events,
    )
