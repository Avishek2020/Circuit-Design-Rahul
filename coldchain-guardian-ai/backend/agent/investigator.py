"""
ColdChain Guardian AI — investigation agent.

Uses Claude claude-sonnet-4-6 with tool_use to investigate cold-chain incidents.
Falls back to a deterministic mock when no ANTHROPIC_API_KEY is set or
force_mock=True — useful for testing and demos without an API key.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.agent.report import Finding, InvestigationReport
from backend.agent.tools import (
    TOOL_SCHEMAS,
    load_synthetic_data,
    tool_get_fleet_summary,
    tool_get_shipment_analysis,
    tool_list_problem_shipments,
    tool_search_sop_documents,
)

# ── system prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are ColdChain Guardian AI, an expert food-safety investigator specialising in \
cold-chain logistics. Your role is to analyse temperature excursion data, identify \
root causes, assess regulatory risk, and recommend corrective actions.

Investigation protocol:
1. For fleet-wide queries: call get_fleet_summary once, then list_problem_shipments,
   then get_shipment_analysis for the TOP 3 worst shipments only (not all of them).
2. For specific shipment queries: call get_shipment_analysis for each mentioned ID.
3. Call search_sop_documents once for the applicable compliance standard.
4. Assess whether the incident meets FDA 21 CFR Part 1 / FSMA regulatory reporting threshold.
5. ALWAYS finish by calling submit_investigation_report with your structured findings.

Rules:
- You MUST call submit_investigation_report — never end with plain text.
- Analyse at most 3–5 shipments per investigation to stay within tool-call limits.
- Cite specific timestamps, temperatures, and SOP sections as evidence.
- Risk level = worst individual finding severity (CRITICAL if any finding is critical).
- regulatory_reportable = true if: pharma product, financial_loss > $10,000, or critical excursion.
"""

# ── tool dispatcher ───────────────────────────────────────────────────────────

class ColdChainInvestigator:
    """
    Main investigation agent.

    Parameters
    ----------
    data_dir    : Path to synthetic JSON data directory (defaults to data/synthetic).
    force_mock  : Skip the Claude API and return a deterministic analysis.
    retriever   : Optional HybridRetriever for SOP semantic search.
    """

    MAX_ITERATIONS = 25   # safety guard on agentic loop

    def __init__(
        self,
        data_dir:    Path | None = None,
        force_mock:  bool = False,
        retriever:   Any = None,
    ) -> None:
        self._data_dir  = data_dir or ROOT / "data" / "synthetic"
        self._retriever = retriever
        self._data: dict[str, list[dict]] | None = None

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._use_mock = force_mock or not api_key

        if not self._use_mock:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        else:
            self._client = None

    # ── public API ────────────────────────────────────────────────────────────

    def investigate(self, query: str) -> InvestigationReport:
        """Run a full investigation on the given natural-language query."""
        if self._use_mock:
            return self._mock_investigate(query)
        return self._run_agent_loop(query)

    # ── data helpers ──────────────────────────────────────────────────────────

    def _get_data(self) -> dict[str, list[dict]]:
        if self._data is None:
            self._data = load_synthetic_data(self._data_dir)
        return self._data

    # ── real Claude agent loop ────────────────────────────────────────────────

    def _run_agent_loop(self, query: str) -> InvestigationReport:
        messages: list[dict] = [{"role": "user", "content": query}]
        shipments_seen: list[str] = []
        report_input: dict | None = None

        for _ in range(self.MAX_ITERATIONS):
            response = self._client.messages.create(   # type: ignore[union-attr]
                model       = "claude-sonnet-4-6",
                max_tokens  = 4096,
                system      = SYSTEM_PROMPT,
                tools       = TOOL_SCHEMAS,
                messages    = messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Claude finished without calling submit_investigation_report.
                # Force one final turn with tool_choice to get a structured report.
                messages.append({
                    "role": "user",
                    "content": (
                        "Please now call submit_investigation_report with your "
                        "structured findings based on the evidence gathered above."
                    ),
                })
                forced = self._client.messages.create(   # type: ignore[union-attr]
                    model       = "claude-sonnet-4-6",
                    max_tokens  = 4096,
                    system      = SYSTEM_PROMPT,
                    tools       = TOOL_SCHEMAS,
                    tool_choice = {"type": "tool", "name": "submit_investigation_report"},
                    messages    = messages,
                )
                for block in forced.content:
                    if getattr(block, "type", None) == "tool_use" \
                            and block.name == "submit_investigation_report":
                        report_input = block.input
                        break
                break   # exit loop regardless

            if response.stop_reason != "tool_use":
                break

            tool_results: list[dict] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                name  = block.name
                inputs = block.input or {}

                if name == "submit_investigation_report":
                    report_input = inputs
                    # Acknowledge the tool call so the loop can exit cleanly
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     "Report submitted.",
                    })
                else:
                    result = self._execute_tool(name, inputs, shipments_seen)
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     json.dumps(result, default=str),
                    })

            messages.append({"role": "user", "content": tool_results})

            if report_input is not None:
                break

        if report_input:
            return self._build_report(query, report_input, shipments_seen)

        return self._text_fallback_report(query, "Investigation incomplete.", shipments_seen)

    def _execute_tool(
        self,
        name:          str,
        inputs:        dict,
        shipments_seen: list[str],
    ) -> Any:
        data = self._get_data()

        if name == "get_shipment_analysis":
            sid = inputs.get("shipment_id", "")
            if sid and sid.upper() not in shipments_seen:
                shipments_seen.append(sid.upper())
            return tool_get_shipment_analysis(sid, data)

        if name == "get_fleet_summary":
            return tool_get_fleet_summary(data)

        if name == "list_problem_shipments":
            return tool_list_problem_shipments(
                data,
                limit         = inputs.get("limit", 10),
                status_filter = inputs.get("status_filter"),
            )

        if name == "search_sop_documents":
            return tool_search_sop_documents(inputs.get("query", ""), self._retriever)

        return {"error": f"Unknown tool: {name}"}

    # ── mock investigation (no API key needed) ────────────────────────────────

    def _mock_investigate(self, query: str) -> InvestigationReport:
        """
        Deterministic investigation without calling the Claude API.
        Extracts shipment IDs from the query, runs temporal analysis,
        and builds a structured report from the results.
        """
        data = self._get_data()

        # Extract entity IDs from query
        sid_matches = re.findall(r"\bSHP-\d+\b", query.upper())
        tid_matches = re.findall(r"\bTRK-\d+\b", query.upper())

        shipments_to_analyze: list[str] = list(dict.fromkeys(sid_matches))

        # If no specific shipment, check for fleet-level keywords
        fleet_keywords = {
            "fleet", "all shipments", "overview", "summary", "worst", "problem",
            "overdue", "maintenance", "all trucks", "compliance", "non-compliant",
            "regulatory", "financial", "total loss", "highest risk",
        }
        is_fleet_query = any(kw in query.lower() for kw in fleet_keywords)

        if not shipments_to_analyze and not is_fleet_query:
            # Try truck-based lookup
            if tid_matches:
                tid = tid_matches[0]
                shipments_to_analyze = [
                    s["shipment_id"] for s in data["shipments"]
                    if s.get("truck_id") == tid
                ][:3]

        if not shipments_to_analyze and not is_fleet_query:
            # Fall back to worst problem shipment
            problems = tool_list_problem_shipments(data, limit=1)
            if problems:
                shipments_to_analyze = [problems[0]["shipment_id"]]

        findings: list[Finding] = []
        all_correlations: list[str] = []
        max_risk = 0.0
        reg_reportable = False

        # Analyse each shipment
        for sid in shipments_to_analyze:
            result = tool_get_shipment_analysis(sid, data)
            if "error" in result:
                continue

            risk = result["risk_score"]
            max_risk = max(max_risk, risk)

            # Build findings from evidence summary sections
            if result["excursion_windows"] > 0:
                sev = "critical" if risk >= 8 else "high" if risk >= 6 else "medium"
                findings.append(Finding(
                    title    = f"{sid}: {result['excursion_windows']} temperature excursion window(s)",
                    detail   = (
                        f"Risk score {risk:.1f}/10 ({result['risk_label']}). "
                        f"{result['total_readings']} readings analysed. "
                        f"MKT: {result['mkt_celsius']:.2f}°C" if result['mkt_celsius'] else
                        f"Risk score {result['risk_score']:.1f}/10 ({result['risk_label']}). "
                        f"{result['total_readings']} readings analysed."
                    ),
                    severity = sev,
                    evidence = [result["evidence_summary"].split("\n")[1]],  # risk line
                ))

            for corr_text in result.get("correlations", []):
                findings.append(Finding(
                    title    = f"{sid}: correlation detected",
                    detail   = corr_text[:300],
                    severity = "high",
                    evidence = [corr_text[:200]],
                ))
                all_correlations.append(corr_text)

            # Pharma or high financial loss → regulatory
            shp = next((s for s in data["shipments"] if s["shipment_id"] == sid), {})
            incs = [i for i in data["incidents"] if i["shipment_id"] == sid]
            loss = sum(i.get("financial_loss_usd", 0) or 0 for i in incs)
            if shp.get("product_category") == "pharma" or loss > 10_000 or risk >= 8:
                reg_reportable = True

        # Fleet-level findings
        fleet_summary: dict = {}
        if is_fleet_query or not shipments_to_analyze:
            fleet_summary = tool_get_fleet_summary(data)
            overdue_trucks = fleet_summary.get("trucks_maintenance_overdue", [])
            findings.append(Finding(
                title    = "Fleet overview",
                detail   = (
                    f"{fleet_summary['total_shipments']} total shipments; "
                    f"{fleet_summary['shipments_with_excursion']} with excursions; "
                    f"{fleet_summary['total_incidents']} incidents; "
                    f"${fleet_summary['total_financial_loss_usd']:,} total loss."
                ),
                severity = "medium" if fleet_summary.get("shipments_with_excursion", 0) > 0 else "low",
                evidence = [
                    f"Trucks overdue for maintenance: "
                    f"{', '.join(overdue_trucks) or 'none'}"
                ],
            ))
            # Derive fleet-level risk from excursion rate + incident count
            n_exc    = fleet_summary.get("shipments_with_excursion", 0)
            n_shp    = max(1, fleet_summary.get("total_shipments", 1))
            n_inc    = fleet_summary.get("total_incidents", 0)
            fleet_risk = min(10.0, n_exc / n_shp * 10 + n_inc * 0.3)
            max_risk   = max(max_risk, fleet_risk)

        # Risk level
        if max_risk >= 8:
            risk_level = "CRITICAL"
        elif max_risk >= 6:
            risk_level = "HIGH"
        elif max_risk >= 4:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Summary sentence
        if shipments_to_analyze:
            summary = (
                f"Analysed {len(shipments_to_analyze)} shipment(s): "
                f"{', '.join(shipments_to_analyze)}. "
                f"Overall risk: {risk_level}. "
                f"{'Regulatory reporting may be required.' if reg_reportable else 'No regulatory reporting threshold met.'}"
            )
        else:
            n_exc = fleet_summary.get("shipments_with_excursion", 0)
            n_shp = fleet_summary.get("total_shipments", 0)
            summary = (
                f"Fleet-wide analysis: {n_shp} shipments, "
                f"{n_exc} with temperature excursions "
                f"({n_exc / max(1, n_shp) * 100:.0f}% non-compliant)."
            )

        actions = [
            "Quarantine affected shipment(s) pending product disposition decision.",
            "Notify QA and regulatory affairs teams immediately for critical findings.",
            "Schedule full refrigeration audit for trucks involved in excursion events.",
            "Review SOP-001 §6 temperature monitoring procedures with driver team.",
            "Update corrective action log and document root cause analysis within 24 h.",
        ]

        citations = [
            "SOP-001 §6.2 — During Transit Temperature Monitoring",
            "SOP-002 §3.1 — Notification Chain (Cold-Chain Breach Response)",
            "SOP-004 §3.1 — Initial Incident Report (Any Employee)",
        ]

        return InvestigationReport(
            query                 = query,
            summary               = summary,
            findings              = findings,
            sop_citations         = citations,
            recommended_actions   = actions,
            risk_level            = risk_level,
            regulatory_reportable = reg_reportable,
            shipments_analyzed    = shipments_to_analyze,
        )

    # ── report builder ────────────────────────────────────────────────────────

    def _build_report(
        self,
        query:          str,
        report_input:   dict,
        shipments_seen: list[str],
    ) -> InvestigationReport:
        findings = [
            Finding(
                title    = f["title"],
                detail   = f["detail"],
                severity = f.get("severity", "medium"),
                evidence = f.get("evidence", []),
            )
            for f in report_input.get("findings", [])
        ]
        return InvestigationReport(
            query                 = query,
            summary               = report_input.get("summary", ""),
            findings              = findings,
            sop_citations         = report_input.get("sop_citations", []),
            recommended_actions   = report_input.get("recommended_actions", []),
            risk_level            = report_input.get("risk_level", "MEDIUM"),
            regulatory_reportable = report_input.get("regulatory_reportable", False),
            shipments_analyzed    = shipments_seen,
        )

    def _text_fallback_report(
        self,
        query:          str,
        text:           str,
        shipments_seen: list[str],
    ) -> InvestigationReport:
        return InvestigationReport(
            query                 = query,
            summary               = text[:500],
            findings              = [],
            sop_citations         = [],
            recommended_actions   = ["Review investigation output manually."],
            risk_level            = "MEDIUM",
            regulatory_reportable = False,
            shipments_analyzed    = shipments_seen,
        )
