"""
Hybrid retrieval: combines semantic (vector) search over SOP documents
with structured SQL queries over logistics data.

Usage:
    retriever = HybridRetriever()
    ctx = retriever.retrieve("What happened on shipment SHP-0023?")
    print(ctx.to_context_string())
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass, field
from typing import Any

from backend.ingestion.embedder import EmbedderBase
from backend.retrieval.semantic import SemanticResult, semantic_search
from backend.retrieval.sql_filter import (
    extract_entity_ids,
    get_door_events,
    get_fleet_summary,
    get_high_severity_incidents,
    get_incident,
    get_incidents_for_shipment,
    get_incidents_for_truck,
    get_maintenance_history,
    get_problem_shipments,
    get_shipment,
    get_shipment_full_context,
    get_suspicious_door_events,
    get_temperature_summary,
    get_truck,
    get_warehouse,
)


# ── context dataclass ─────────────────────────────────────────────────────────

@dataclass
class RetrievalContext:
    query: str
    entities: dict[str, list[str]]           # extracted IDs per type
    semantic_results: list[SemanticResult]   # SOP document chunks
    shipments: list[dict[str, Any]]
    trucks: list[dict[str, Any]]
    warehouses: list[dict[str, Any]]
    incidents: list[dict[str, Any]]
    temperature_summaries: list[dict[str, Any]]
    door_events: list[dict[str, Any]]
    maintenance_reports: list[dict[str, Any]]

    # ── rendering ─────────────────────────────────────────────────────────────

    def to_context_string(self) -> str:
        """
        Renders the full retrieval context as a structured text block
        suitable for injecting into an AI agent prompt.
        Each section begins with a header and ends with a blank line.
        """
        parts: list[str] = []

        # 1. Document knowledge base
        if self.semantic_results:
            parts.append("=== REGULATORY / SOP KNOWLEDGE BASE ===")
            for r in self.semantic_results:
                parts.append(
                    f"[{r.citation} | relevance={r.score:.2f}]\n"
                    + textwrap.fill(r.text[:800], width=100)
                )
            parts.append("")

        # 2. Shipments
        if self.shipments:
            parts.append("=== SHIPMENT RECORDS ===")
            for s in self.shipments:
                parts.append(self._fmt_shipment(s))
            parts.append("")

        # 3. Trucks
        if self.trucks:
            parts.append("=== TRUCK RECORDS ===")
            for t in self.trucks:
                parts.append(self._fmt_truck(t))
            parts.append("")

        # 4. Warehouses
        if self.warehouses:
            parts.append("=== WAREHOUSE RECORDS ===")
            for w in self.warehouses:
                parts.append(self._fmt_warehouse(w))
            parts.append("")

        # 5. Incidents
        if self.incidents:
            parts.append("=== INCIDENT RECORDS ===")
            for inc in self.incidents:
                parts.append(self._fmt_incident(inc))
            parts.append("")

        # 6. Temperature summaries
        if self.temperature_summaries:
            parts.append("=== TEMPERATURE EXCURSION SUMMARIES ===")
            for ts in self.temperature_summaries:
                parts.append(self._fmt_temp_summary(ts))
            parts.append("")

        # 7. Door events
        if self.door_events:
            parts.append("=== DOOR EVENTS ===")
            for de in self.door_events:
                parts.append(self._fmt_door_event(de))
            parts.append("")

        # 8. Maintenance
        if self.maintenance_reports:
            parts.append("=== MAINTENANCE HISTORY ===")
            for mr in self.maintenance_reports:
                parts.append(self._fmt_maintenance(mr))
            parts.append("")

        if not parts:
            return "(No relevant data found for this query.)"
        return "\n".join(parts)

    # ── formatters ────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_shipment(s: dict) -> str:
        return (
            f"[{s['shipment_id']} | {s['truck_id']} | {s['product_type']}]\n"
            f"  Status:   {s['status']}\n"
            f"  Route:    {s['origin_warehouse_id']} → {s['destination_warehouse_id']}\n"
            f"  Departed: {s.get('departure_time', 'N/A')}\n"
            f"  Arrived:  {s.get('arrival_time', 'N/A')}\n"
            f"  Temp req: {s['required_temp_min']}°C to {s['required_temp_max']}°C\n"
            f"  Quantity: {s['quantity_kg']} kg | Driver: {s['driver_name']}\n"
            + (f"  Notes:    {s['notes']}" if s.get("notes") else "")
        )

    @staticmethod
    def _fmt_truck(t: dict) -> str:
        return (
            f"[{t['truck_id']} | {t['make']} {t['model']} {t['year']}]\n"
            f"  Status:          {t['current_status']}\n"
            f"  Driver:          {t['assigned_driver']}\n"
            f"  Refrigeration:   {t['refrigeration_unit']}\n"
            f"  Last maint:      {t['last_maintenance_date']}\n"
            f"  Next maint due:  {t['next_maintenance_due']}\n"
            + (f"  Notes:           {t['notes']}" if t.get("notes") else "")
        )

    @staticmethod
    def _fmt_warehouse(w: dict) -> str:
        certs = ", ".join(w.get("certifications") or [])
        return (
            f"[{w['warehouse_id']} | {w['name']}]\n"
            f"  Location:   {w['location']}\n"
            f"  Capacity:   {w['capacity_pallets']} pallets "
            f"({w['current_occupancy_pallets']} occupied)\n"
            f"  Certifications: {certs}"
        )

    @staticmethod
    def _fmt_incident(i: dict) -> str:
        flag = " ⚠ REGULATORY REPORTABLE" if i.get("regulatory_reportable") else ""
        return (
            f"[{i['incident_id']} | {i['shipment_id']} | {i['severity'].upper()}]{flag}\n"
            f"  Type:       {i['type']}\n"
            f"  When:       {i.get('timestamp', 'N/A')}\n"
            f"  Duration:   {i['duration_minutes']} min\n"
            f"  Deviation:  +{i['max_temp_deviation']}°C above limit\n"
            f"  Root cause: {i['root_cause']}\n"
            f"  Disposed:   {i['disposal_kg']} kg | Loss: ${i['financial_loss_usd']:,}\n"
            f"  Action:     {i['corrective_action']}\n"
            f"  Investigator: {i['investigator']} | Status: {i['status']}"
        )

    @staticmethod
    def _fmt_temp_summary(ts: dict) -> str:
        exc = ts["excursion_count"]
        flag = " ⚠ EXCURSIONS DETECTED" if exc > 0 else " ✓ No excursions"
        return (
            f"[{ts['shipment_id']} temperature summary]{flag}\n"
            f"  Readings:        {ts['total_readings']}\n"
            f"  Excursion count: {exc}\n"
            f"  Temp range:      {ts['min_temp']}°C – {ts['max_temp']}°C\n"
            f"  Avg temp:        {ts['avg_temp']}°C\n"
            + (f"  First excursion: {ts['first_excursion_at']}" if ts.get("first_excursion_at") else "")
        )

    @staticmethod
    def _fmt_door_event(de: dict) -> str:
        flag = " ⚠ UNSCHEDULED" if not de.get("is_scheduled_stop") else ""
        dur  = f" ({de['duration_seconds']}s)" if de.get("duration_seconds") else ""
        note = f" – {de['notes']}" if de.get("notes") else ""
        return (
            f"  {de['event_id']} | {de['event_type'].upper()}{dur}{flag}{note}\n"
            f"    Time: {de['timestamp']} | "
            f"Lat: {de['location_lat']:.4f}, Lon: {de['location_lon']:.4f}"
        )

    @staticmethod
    def _fmt_maintenance(mr: dict) -> str:
        status = "PASS" if mr.get("passed_inspection") else "⚠ FAIL"
        issues = ", ".join(mr.get("issues_found") or []) or "none"
        parts  = ", ".join(mr.get("parts_replaced") or []) or "none"
        return (
            f"[{mr['report_id']} | {mr['truck_id']} | {mr['date']} | {status}]\n"
            f"  Type:     {mr['type']}\n"
            f"  Issues:   {issues}\n"
            f"  Parts:    {parts}\n"
            f"  Cost:     ${mr['cost_usd']:,} | Tech: {mr['technician']}"
        )


# ── retriever ─────────────────────────────────────────────────────────────────

class HybridRetriever:
    def __init__(self, semantic_top_k: int = 5):
        self.semantic_top_k = semantic_top_k

    def retrieve(self, query: str) -> RetrievalContext:
        """
        Main entry point.  Given a natural-language query:
          1. Extract entity IDs (SHP-XXXX, TRK-XXX, etc.)
          2. Run semantic search over SOP documents
          3. Fetch structured SQL data for each detected entity
          4. Return a RetrievalContext with everything combined
        """
        entities = extract_entity_ids(query)
        sem      = semantic_search(query, top_k=self.semantic_top_k)

        shipments:     list[dict] = []
        trucks:        list[dict] = []
        warehouses:    list[dict] = []
        incidents:     list[dict] = []
        temp_sums:     list[dict] = []
        door_evs:      list[dict] = []
        maint_reports: list[dict] = []

        # Shipment-centric context
        for sid in entities.get("shipment", []):
            ctx = get_shipment_full_context(sid)
            if "error" in ctx:
                continue
            if ctx["shipment"]:
                shipments.append(ctx["shipment"])
            if ctx["truck"] and ctx["truck"] not in trucks:
                trucks.append(ctx["truck"])
            for wh in [ctx["origin_warehouse"], ctx["destination_warehouse"]]:
                if wh and wh not in warehouses:
                    warehouses.append(wh)
            incidents.extend(ctx["incidents"])
            if ctx["temperature_summary"]:
                temp_sums.append(ctx["temperature_summary"])
            door_evs.extend(ctx["door_events"])
            maint_reports.extend(ctx["maintenance_history"])

        # Direct truck lookups
        for tid in entities.get("truck", []):
            t = get_truck(tid)
            if t and t not in trucks:
                trucks.append(t)
            for inc in get_incidents_for_truck(tid):
                if inc not in incidents:
                    incidents.append(inc)
            for mr in get_maintenance_history(tid):
                if mr not in maint_reports:
                    maint_reports.append(mr)

        # Direct warehouse lookups
        for wid in entities.get("warehouse", []):
            w = get_warehouse(wid)
            if w and w not in warehouses:
                warehouses.append(w)

        # Direct incident lookups
        for iid in entities.get("incident", []):
            inc = get_incident(iid)
            if inc and inc not in incidents:
                incidents.append(inc)
                # pull the linked shipment/truck if not already present
                if inc.get("shipment_id"):
                    ctx = get_shipment_full_context(inc["shipment_id"])
                    if "error" not in ctx:
                        if ctx["shipment"] and ctx["shipment"] not in shipments:
                            shipments.append(ctx["shipment"])
                        if ctx["temperature_summary"]:
                            temp_sums.append(ctx["temperature_summary"])

        # Keyword fallbacks when no entity IDs detected
        if not entities:
            q_lower = query.lower()
            if any(w in q_lower for w in ["excursion", "temperature", "breach", "incident"]):
                incidents = get_high_severity_incidents(limit=5)
            if any(w in q_lower for w in ["fleet", "summary", "overview", "statistics"]):
                # attach a synthetic "fleet summary" as a fake shipment block
                pass  # fleet_summary surfaced via sql_filter.get_fleet_summary() directly

        # Deduplicate by natural key
        incidents = _dedup(incidents, "incident_id")
        maint_reports = _dedup(maint_reports, "report_id")
        door_evs  = _dedup(door_evs,  "event_id")
        temp_sums = _dedup(temp_sums, "shipment_id")

        return RetrievalContext(
            query                = query,
            entities             = entities,
            semantic_results     = sem,
            shipments            = shipments,
            trucks               = trucks,
            warehouses           = warehouses,
            incidents            = incidents,
            temperature_summaries= temp_sums,
            door_events          = door_evs,
            maintenance_reports  = maint_reports,
        )


def _dedup(records: list[dict], key: str) -> list[dict]:
    seen: set = set()
    out: list[dict] = []
    for r in records:
        v = r.get(key)
        if v not in seen:
            seen.add(v)
            out.append(r)
    return out
