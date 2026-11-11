#!/usr/bin/env python
"""
ColdChain Guardian AI — interactive demo runner.

Exercises 8 investigation scenarios end-to-end and prints a formatted
report to the terminal.  No database or API key required (uses mock mode).

Usage:
    python scripts/demo.py
    python scripts/demo.py --live     # requires ANTHROPIC_API_KEY
"""

from __future__ import annotations

import sys
import time
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.agent.investigator import ColdChainInvestigator
from backend.agent.tools import load_synthetic_data, tool_get_fleet_summary, _clear_cache


# ── ANSI colours ──────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
ORANGE = "\033[33m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"

RISK_COLOUR = {
    "CRITICAL": RED, "HIGH": ORANGE, "MEDIUM": YELLOW, "LOW": GREEN,
    "critical": RED, "high": ORANGE, "medium": YELLOW, "low": GREEN,
}
SEV_ICON = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🚨"}

def _risk(level: str) -> str:
    c = RISK_COLOUR.get(level, WHITE)
    return f"{c}{BOLD}{level}{RESET}"

def _hr(char="─", n=72) -> str:
    return DIM + char * n + RESET

def _header(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{text}{RESET}")
    print(_hr())


# ── demo scenarios ────────────────────────────────────────────────────────────

SCENARIOS = [
    ("Fleet Health Overview",
     "Give me a fleet overview including all problem shipments and financial losses"),

    ("Worst Temperature Excursion",
     "Investigate the shipment with the worst temperature excursion this period"),

    ("Maintenance Risk Assessment",
     "Which trucks are overdue for maintenance and what risk do they pose?"),

    ("Regulatory Compliance Check",
     "Are there any incidents that require FDA or FSMA regulatory reporting?"),

    ("Door-Excursion Correlation",
     "Were any temperature excursions caused by unscheduled door openings?"),

    ("Pharma Cold-Chain Integrity",
     "Analyse pharmaceutical shipments for cold-chain integrity failures"),

    ("Night-Stop Security Analysis",
     "Were there any unscheduled night-time door openings that could indicate tampering?"),

    ("Financial Impact Summary",
     "What is the total financial impact of cold-chain failures and which shipments caused it?"),
]


def run_demo(force_mock: bool = True) -> None:
    _clear_cache()
    data = load_synthetic_data(ROOT / "data" / "synthetic")
    fleet = tool_get_fleet_summary(data)

    print("\n" + "═" * 72)
    print(f"  {BOLD}{CYAN}ColdChain Guardian AI{RESET} — Investigation Demo")
    print("═" * 72)
    print(f"  Mode:        {'mock (no API key)' if force_mock else BOLD + GREEN + 'LIVE (Claude claude-sonnet-4-6)' + RESET}")
    print(f"  Shipments:   {fleet['total_shipments']} total | "
          f"{RED}{fleet['shipments_with_excursion']} with excursions{RESET}")
    print(f"  Incidents:   {fleet['total_incidents']} | "
          f"Financial loss: ${fleet['total_financial_loss_usd']:,.0f}")
    print(f"  Maint. due:  {', '.join(fleet['trucks_maintenance_overdue']) or 'none'}")
    print("═" * 72 + "\n")

    inv = ColdChainInvestigator(
        data_dir   = ROOT / "data" / "synthetic",
        force_mock = force_mock,
    )

    total_time = 0.0
    results    = []

    for i, (title, query) in enumerate(SCENARIOS, 1):
        _header(f"Scenario {i}/{len(SCENARIOS)}: {title}")
        print(f"{DIM}Query: {query}{RESET}\n")

        t0 = time.perf_counter()
        try:
            report  = inv.investigate(query)
            elapsed = time.perf_counter() - t0
            total_time += elapsed

            print(f"  Risk Level:  {_risk(report.risk_level)}  "
                  f"{DIM}({elapsed:.2f}s){RESET}")
            print(f"  Regulatory:  {'⚠ YES' if report.regulatory_reportable else 'No'}")
            print(f"  Shipments:   {', '.join(report.shipments_analyzed) or '—'}")
            print()
            print(f"  {BOLD}Summary:{RESET} {report.summary}")

            if report.findings:
                print(f"\n  {BOLD}Findings ({len(report.findings)}):{RESET}")
                for f in report.findings[:3]:
                    icon = SEV_ICON.get(f.severity, "·")
                    print(f"    {icon} {f.title}")
                    print(f"       {DIM}{f.detail[:100]}{'…' if len(f.detail) > 100 else ''}{RESET}")
                if len(report.findings) > 3:
                    print(f"    {DIM}… {len(report.findings) - 3} more finding(s){RESET}")

            if report.sop_citations:
                print(f"\n  {BOLD}SOP Citations:{RESET}")
                for c in report.sop_citations[:3]:
                    print(f"    📋 {BLUE}{c}{RESET}")

            if report.recommended_actions:
                print(f"\n  {BOLD}Top Action:{RESET} {report.recommended_actions[0]}")

            results.append(("✓", title, report.risk_level, elapsed))

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"  {RED}ERROR: {exc}{RESET}")
            results.append(("✗", title, "ERROR", elapsed))

    # ── summary table ─────────────────────────────────────────────────────────
    print("\n\n" + "═" * 72)
    print(f"  {BOLD}DEMO SUMMARY{RESET}")
    print("═" * 72)
    print(f"  {'#':<3} {'Scenario':<42} {'Risk':<10} {'Time':>7}")
    print("  " + "─" * 68)
    for j, (status, title, level, t) in enumerate(results, 1):
        rc = RISK_COLOUR.get(level, WHITE)
        print(f"  {status} {j:<2} {title:<42} {rc}{level:<10}{RESET} {t:>6.2f}s")
    print("  " + "─" * 68)
    passed = sum(1 for s, *_ in results if s == "✓")
    print(f"  {GREEN if passed == len(results) else RED}"
          f"{passed}/{len(results)} scenarios passed{RESET}"
          f"  |  Total: {total_time:.2f}s  |  Avg: {total_time/len(results):.2f}s")
    print("═" * 72 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ColdChain Guardian AI demo")
    parser.add_argument("--live", action="store_true",
                        help="Use real Claude API (requires ANTHROPIC_API_KEY)")
    args = parser.parse_args()
    run_demo(force_mock=not args.live)
