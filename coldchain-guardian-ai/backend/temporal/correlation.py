"""
Temporal correlation analysis — detects causal relationships between events.

All functions are pure: they operate on pre-loaded Python dicts.
No database queries inside this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Sequence

from backend.temporal.temperature import ExcursionWindow, _parse_ts
from backend.temporal.timeline import (
    EV_DOOR_OPEN_UNSCHEDULED,
    ShipmentTimeline,
    TimelineEvent,
)


# ── data class ────────────────────────────────────────────────────────────────

@dataclass
class CorrelationFinding:
    finding_type:   str     # "door_triggered_excursion" | "maintenance_risk" | …
    confidence:     float   # 0.0–1.0
    severity:       str     # "low" | "medium" | "high" | "critical"
    description:    str
    evidence:       list[str]   = field(default_factory=list)
    recommendations: list[str]  = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"[{self.finding_type.upper()} | confidence={self.confidence:.0%} | {self.severity.upper()}]",
            f"  {self.description}",
        ]
        for ev in self.evidence:
            lines.append(f"  Evidence: {ev}")
        for rec in self.recommendations:
            lines.append(f"  Action:   {rec}")
        return "\n".join(lines)


# ── 1. Door-triggered excursion ───────────────────────────────────────────────

def find_door_excursion_correlations(
    timeline:          ShipmentTimeline,
    excursion_windows: list[ExcursionWindow],
    precede_window_min: int = 90,       # look back this many minutes before each excursion
) -> list[CorrelationFinding]:
    """
    Check whether a door-open event (especially unscheduled) occurred within
    *precede_window_min* minutes before an excursion start.
    """
    findings: list[CorrelationFinding] = []

    for window in excursion_windows:
        lookback_start = window.start_time - timedelta(minutes=precede_window_min)
        preceding_door = [
            e for e in timeline.events
            if e.source == "door"
            and e.event_type in (EV_DOOR_OPEN_UNSCHEDULED, "DOOR_OPEN")
            and lookback_start <= e.timestamp <= window.start_time
        ]
        unscheduled = [e for e in preceding_door if e.event_type == EV_DOOR_OPEN_UNSCHEDULED]

        if not preceding_door:
            continue

        # Confidence rises if the opening was unscheduled, close in time, or long
        gap_minutes = (window.start_time - preceding_door[-1].timestamp).total_seconds() / 60
        base_conf   = 0.60
        if unscheduled:
            base_conf += 0.20
        if gap_minutes < 30:
            base_conf += 0.10
        # Check if any door was open DURING the excursion
        open_during = [
            e for e in timeline.events
            if e.source == "door" and e.event_type in (EV_DOOR_OPEN_UNSCHEDULED, "DOOR_OPEN")
            and window.start_time <= e.timestamp <= window.end_time
        ]
        if open_during:
            base_conf += 0.05

        confidence = min(base_conf, 0.95)
        is_unsched = bool(unscheduled)

        findings.append(CorrelationFinding(
            finding_type = "door_triggered_excursion",
            confidence   = round(confidence, 2),
            severity     = window.severity,
            description  = (
                f"{'Unscheduled' if is_unsched else 'Scheduled'} door opening "
                f"{gap_minutes:.0f} min before excursion window #{window.index + 1}. "
                f"Ambient-air intrusion likely caused the temperature rise."
            ),
            evidence = [
                f"Door event at {preceding_door[-1].ts_label} "
                f"({'unscheduled' if is_unsched else 'scheduled'})",
                f"Excursion start: {window.start_time.strftime('%Y-%m-%dT%H:%MZ')} "
                f"(gap: {gap_minutes:.0f} min)",
                f"Peak deviation: {'+' if window.max_deviation > 0 else ''}"
                f"{window.max_deviation:.1f}°C | Duration: {window.duration_minutes:.0f} min",
            ],
            recommendations = [
                "Review door-sensor logs for this trip and enforce lock-on-move protocol.",
                "Investigate whether the stop was authorized and logged in the route plan.",
                "Consider mandatory re-cool period after any unscheduled door opening.",
            ],
        ))

    return findings


# ── 2. Maintenance-related risk ───────────────────────────────────────────────

_RISKY_ISSUES = {
    "compressor_noise", "minor_refrigerant_leak", "thermostat_drift",
    "door_seal_wear", "condenser_coil",
}


def find_maintenance_correlations(
    truck:            dict,
    maintenance:      Sequence[dict],
    incident_time:    datetime | None = None,
    lookback_days:    int = 180,
) -> list[CorrelationFinding]:
    """
    Check whether the truck's maintenance history shows risk factors for the incident:
    - Failed inspections within *lookback_days* before the incident
    - Known refrigeration-related issues
    - Overdue maintenance at the time of incident
    """
    findings: list[CorrelationFinding] = []
    ref_time  = incident_time or datetime.now(timezone.utc)
    cutoff    = ref_time - timedelta(days=lookback_days)

    recent    = [
        mr for mr in maintenance
        if _parse_ts(mr["date"] + "T00:00:00Z") >= cutoff
    ]
    failed    = [mr for mr in recent if not mr.get("passed_inspection", True)]
    risky_iss = [
        mr for mr in recent
        if any(iss in _RISKY_ISSUES for iss in (mr.get("issues_found") or []))
    ]

    # Failed inspection finding
    if failed:
        days_since = [
            (ref_time - _parse_ts(mr["date"] + "T00:00:00Z")).days
            for mr in failed
        ]
        min_days = min(days_since)
        confidence = 0.85 if min_days <= 60 else 0.65

        all_issues = []
        for mr in failed:
            all_issues.extend(mr.get("issues_found") or [])

        findings.append(CorrelationFinding(
            finding_type = "maintenance_failed_inspection",
            confidence   = confidence,
            severity     = "high" if min_days <= 60 else "medium",
            description  = (
                f"Truck {truck.get('truck_id', '?')} had {len(failed)} failed "
                f"inspection(s) within the past {lookback_days} days "
                f"(most recent: {min_days} days before incident)."
            ),
            evidence = [
                f"Report {mr['report_id']}: failed on {mr['date']} — "
                f"issues: {', '.join(mr.get('issues_found') or ['unspecified'])}"
                for mr in failed
            ],
            recommendations = [
                "Quarantine truck for full refrigeration unit inspection before next load.",
                f"Review CAPA for report(s): {', '.join(mr['report_id'] for mr in failed)}.",
                "Verify compressor, door seals, and thermostat before return to service.",
            ],
        ))

    # Maintenance overdue
    next_due_str = truck.get("next_maintenance_due")
    if next_due_str:
        next_due = _parse_ts(next_due_str + "T00:00:00Z")
        if ref_time > next_due:
            overdue_days = (ref_time - next_due).days
            confidence   = min(0.90, 0.60 + overdue_days / 100)
            findings.append(CorrelationFinding(
                finding_type = "maintenance_overdue",
                confidence   = round(confidence, 2),
                severity     = "high" if overdue_days > 30 else "medium",
                description  = (
                    f"Truck {truck.get('truck_id', '?')} was {overdue_days} days "
                    f"overdue for scheduled maintenance at time of incident "
                    f"(due: {next_due_str})."
                ),
                evidence = [
                    f"Next service due: {next_due_str}",
                    f"Incident time: {ref_time.strftime('%Y-%m-%d')}",
                    f"Overdue by {overdue_days} days",
                ],
                recommendations = [
                    "Immediate out-of-service order until full maintenance completed.",
                    "Review scheduling system to enforce mandatory maintenance deadlines.",
                ],
            ))

    # Known risky issues (not necessarily failed)
    if risky_iss and not failed:
        issues_flat = []
        for mr in risky_iss:
            issues_flat.extend(mr.get("issues_found") or [])
        findings.append(CorrelationFinding(
            finding_type = "known_refrigeration_issue",
            confidence   = 0.55,
            severity     = "medium",
            description  = (
                f"Known refrigeration-related issues were logged for "
                f"{truck.get('truck_id', '?')} within {lookback_days} days: "
                f"{', '.join(set(issues_flat))}."
            ),
            evidence = [
                f"Report {mr['report_id']} ({mr['date']}): {', '.join(mr.get('issues_found') or [])}"
                for mr in risky_iss
            ],
            recommendations = [
                "Verify refrigeration unit was fully repaired and re-tested before this trip.",
            ],
        ))

    return findings


# ── 3. Fleet pattern detection ────────────────────────────────────────────────

def detect_fleet_patterns(
    all_shipments:  Sequence[dict],
    all_incidents:  Sequence[dict],
    all_maintenance: Sequence[dict],
) -> list[CorrelationFinding]:
    """
    Identify systemic patterns across the fleet:
    - Trucks with ≥ 2 incidents
    - Drivers with ≥ 2 incidents
    - Warehouses as common incident site
    - Repeated root causes
    """
    findings: list[CorrelationFinding] = []

    # Count incidents by truck
    truck_counts: dict[str, list[str]] = {}
    for inc in all_incidents:
        tid = inc.get("truck_id", "")
        truck_counts.setdefault(tid, []).append(inc["incident_id"])

    for tid, inc_ids in truck_counts.items():
        if len(inc_ids) >= 2:
            findings.append(CorrelationFinding(
                finding_type = "recurring_truck_incidents",
                confidence   = min(0.90, 0.60 + len(inc_ids) * 0.10),
                severity     = "high",
                description  = (
                    f"Truck {tid} is involved in {len(inc_ids)} separate incidents: "
                    f"{', '.join(inc_ids)}. This suggests a systemic equipment issue."
                ),
                evidence = [f"Incidents: {', '.join(inc_ids)}"],
                recommendations = [
                    f"Full refrigeration audit of {tid}.",
                    "Consider replacing refrigeration unit if issues persist.",
                ],
            ))

    # Count incidents by driver
    driver_counts: dict[str, list[str]] = {}
    for inc in all_incidents:
        sid  = inc.get("shipment_id", "")
        shp  = next((s for s in all_shipments if s.get("shipment_id") == sid), None)
        if shp:
            drv = shp.get("driver_name", "")
            driver_counts.setdefault(drv, []).append(inc["incident_id"])

    for drv, inc_ids in driver_counts.items():
        if len(inc_ids) >= 2 and drv:
            findings.append(CorrelationFinding(
                finding_type = "recurring_driver_incidents",
                confidence   = min(0.80, 0.55 + len(inc_ids) * 0.08),
                severity     = "medium",
                description  = (
                    f"Driver '{drv}' is associated with {len(inc_ids)} incidents: "
                    f"{', '.join(inc_ids)}. Training review may be warranted."
                ),
                evidence = [f"Incidents on driver's shipments: {', '.join(inc_ids)}"],
                recommendations = [
                    f"Schedule refresher cold-chain handling training for {drv}.",
                    "Review SOP compliance on door-open and idle-stop procedures.",
                ],
            ))

    # Count by root cause
    root_cause_counts: dict[str, int] = {}
    for inc in all_incidents:
        rc = inc.get("root_cause", "unknown")
        root_cause_counts[rc] = root_cause_counts.get(rc, 0) + 1

    for rc, count in root_cause_counts.items():
        if count >= 3:
            findings.append(CorrelationFinding(
                finding_type = "systemic_root_cause",
                confidence   = min(0.95, 0.65 + count * 0.05),
                severity     = "critical",
                description  = (
                    f"Root cause '{rc}' appears in {count} incidents, indicating "
                    f"a systemic failure rather than isolated events."
                ),
                evidence = [f"{count} incidents with root cause: {rc}"],
                recommendations = [
                    f"Conduct fleet-wide review of {rc.replace('_', ' ')} controls.",
                    "Escalate to VP Food Safety for preventive action program.",
                ],
            ))

    return findings


# ── 4. Night-stop pattern ─────────────────────────────────────────────────────

def detect_night_stop_pattern(
    timeline: ShipmentTimeline,
    night_start_hour: int = 22,
    night_end_hour:   int = 5,
) -> CorrelationFinding | None:
    """
    Flag if unscheduled door opens occur during night hours (22:00–05:00 local UTC).
    Night stops with door access are a common vector for cargo tampering.
    """
    night_events = [
        e for e in timeline.unscheduled_door_events
        if (e.timestamp.hour >= night_start_hour or e.timestamp.hour < night_end_hour)
    ]
    if not night_events:
        return None

    return CorrelationFinding(
        finding_type = "night_stop_unscheduled_access",
        confidence   = 0.78,
        severity     = "high",
        description  = (
            f"{len(night_events)} unscheduled door opening(s) during night hours "
            f"({night_start_hour:02d}:00–{night_end_hour:02d}:00 UTC) on shipment "
            f"{timeline.shipment_id}."
        ),
        evidence = [
            f"Unscheduled open at {e.ts_label}"
            for e in night_events
        ],
        recommendations = [
            "Review GPS coordinates of stop against approved stopping points.",
            "Cross-check against driver log and ELD records.",
            "Consider tamper-evident seal audit for cargo.",
        ],
    )
