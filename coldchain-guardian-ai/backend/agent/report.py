"""
InvestigationReport — the structured output of the AI agent's analysis.
Pure dataclasses; no DB or API dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Finding:
    title:     str
    detail:    str
    severity:  str           # "low" | "medium" | "high" | "critical"
    evidence:  list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title":    self.title,
            "detail":   self.detail,
            "severity": self.severity,
            "evidence": self.evidence,
        }


@dataclass
class InvestigationReport:
    query:                 str
    summary:               str
    findings:              list[Finding]
    sop_citations:         list[str]
    recommended_actions:   list[str]
    risk_level:            str           # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    regulatory_reportable: bool
    shipments_analyzed:    list[str]
    generated_at:          datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── convenience ──────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "query":                 self.query,
            "summary":               self.summary,
            "findings":              [f.to_dict() for f in self.findings],
            "sop_citations":         self.sop_citations,
            "recommended_actions":   self.recommended_actions,
            "risk_level":            self.risk_level,
            "regulatory_reportable": self.regulatory_reportable,
            "shipments_analyzed":    self.shipments_analyzed,
            "generated_at":          self.generated_at.isoformat(),
        }

    def to_markdown(self) -> str:
        sev_icon = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🚨"}
        risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴", "CRITICAL": "🚨"}

        lines = [
            f"# ColdChain Investigation Report",
            f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Risk Level:** {risk_icon.get(self.risk_level, '')} {self.risk_level}",
            f"**Regulatory Reportable:** {'YES ⚠' if self.regulatory_reportable else 'No'}",
            f"**Shipments Analyzed:** {', '.join(self.shipments_analyzed) or '—'}",
            "",
            "## Query",
            f"> {self.query}",
            "",
            "## Summary",
            self.summary,
        ]

        if self.findings:
            lines += ["", "## Findings"]
            for i, f in enumerate(self.findings, 1):
                icon = sev_icon.get(f.severity, "·")
                lines.append(f"\n### {i}. {icon} {f.title} `[{f.severity.upper()}]`")
                lines.append(f.detail)
                if f.evidence:
                    lines.append("")
                    for ev in f.evidence:
                        lines.append(f"- {ev}")

        if self.sop_citations:
            lines += ["", "## SOP Citations"]
            for c in self.sop_citations:
                lines.append(f"- {c}")

        if self.recommended_actions:
            lines += ["", "## Recommended Actions"]
            for j, action in enumerate(self.recommended_actions, 1):
                lines.append(f"{j}. {action}")

        return "\n".join(lines)
