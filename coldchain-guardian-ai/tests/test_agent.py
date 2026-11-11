"""
Unit + integration tests for the Day 5 AI investigation agent.

All tests are pure-Python (no DB, no Anthropic API key required):
- tool functions are tested directly against synthetic JSON data
- investigator tests use force_mock=True
- FastAPI routes are tested with httpx.AsyncClient / TestClient
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SYNTHETIC = ROOT / "data" / "synthetic"


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_data():
    from backend.agent.tools import load_synthetic_data, _clear_cache
    _clear_cache()
    return load_synthetic_data(SYNTHETIC)


# ── tool function tests ───────────────────────────────────────────────────────

class TestToolGetShipmentAnalysis:
    def test_known_shipment_returns_result(self):
        from backend.agent.tools import tool_get_shipment_analysis
        data   = _load_data()
        sid    = data["shipments"][0]["shipment_id"]
        result = tool_get_shipment_analysis(sid, data)
        assert result["shipment_id"] == sid
        assert "risk_score" in result
        assert "evidence_summary" in result
        assert isinstance(result["excursion_windows"], int)

    def test_unknown_shipment_returns_error(self):
        from backend.agent.tools import tool_get_shipment_analysis
        data   = _load_data()
        result = tool_get_shipment_analysis("SHP-9999", data)
        assert "error" in result

    def test_case_insensitive(self):
        from backend.agent.tools import tool_get_shipment_analysis
        data   = _load_data()
        sid    = data["shipments"][0]["shipment_id"]
        result = tool_get_shipment_analysis(sid.lower(), data)
        assert result["shipment_id"] == sid

    def test_shipment_with_excursion_has_risk_score(self):
        from backend.agent.tools import tool_get_shipment_analysis
        data     = _load_data()
        exc_sids = {r["shipment_id"] for r in data["temperature_readings"]
                    if r.get("is_excursion")}
        assert exc_sids, "Need at least one excursion shipment"
        sid    = sorted(exc_sids)[0]
        result = tool_get_shipment_analysis(sid, data)
        assert result["risk_score"] > 0
        assert result["excursion_windows"] > 0
        assert not result["is_compliant"]


class TestToolGetFleetSummary:
    def test_returns_expected_keys(self):
        from backend.agent.tools import tool_get_fleet_summary
        data   = _load_data()
        result = tool_get_fleet_summary(data)
        for key in [
            "total_shipments", "shipments_with_excursion",
            "total_incidents", "total_financial_loss_usd",
            "status_breakdown", "total_trucks",
        ]:
            assert key in result, f"Missing key: {key}"

    def test_counts_match_data(self):
        from backend.agent.tools import tool_get_fleet_summary
        data   = _load_data()
        result = tool_get_fleet_summary(data)
        assert result["total_shipments"] == len(data["shipments"])
        assert result["total_trucks"]    == len(data["trucks"])

    def test_excursion_count_nonzero(self):
        from backend.agent.tools import tool_get_fleet_summary
        data   = _load_data()
        result = tool_get_fleet_summary(data)
        assert result["shipments_with_excursion"] > 0, "Synthetic data should have excursions"


class TestToolListProblemShipments:
    def test_returns_list(self):
        from backend.agent.tools import tool_list_problem_shipments
        data   = _load_data()
        result = tool_list_problem_shipments(data, limit=5)
        assert isinstance(result, list)
        assert len(result) <= 5

    def test_all_have_excursion_or_incident(self):
        from backend.agent.tools import tool_list_problem_shipments
        data     = _load_data()
        exc_sids = {r["shipment_id"] for r in data["temperature_readings"]
                    if r.get("is_excursion")}
        inc_sids = {i["shipment_id"] for i in data["incidents"]}
        problem  = exc_sids | inc_sids
        result   = tool_list_problem_shipments(data, limit=20)
        for r in result:
            assert r["shipment_id"] in problem

    def test_sorted_by_severity(self):
        from backend.agent.tools import tool_list_problem_shipments
        data   = _load_data()
        result = tool_list_problem_shipments(data, limit=20)
        for i in range(len(result) - 1):
            a, b = result[i], result[i + 1]
            # incident_count descending, then excursion_readings descending
            assert (a["incident_count"], a["excursion_readings"]) >= \
                   (b["incident_count"], b["excursion_readings"])

    def test_status_filter(self):
        from backend.agent.tools import tool_list_problem_shipments
        data   = _load_data()
        result = tool_list_problem_shipments(data, limit=20, status_filter="failed_inspection")
        for r in result:
            assert r["status"] == "failed_inspection"


class TestToolSearchSop:
    def test_no_retriever_returns_note(self):
        from backend.agent.tools import tool_search_sop_documents
        result = tool_search_sop_documents("temperature excursion", retriever=None)
        assert isinstance(result, list)
        assert any("note" in r for r in result)


# ── InvestigationReport tests ─────────────────────────────────────────────────

class TestInvestigationReport:
    def _make_report(self):
        from backend.agent.report import Finding, InvestigationReport
        return InvestigationReport(
            query                 = "What happened to SHP-0007?",
            summary               = "Critical excursion detected.",
            findings              = [
                Finding("Excursion", "12°C above limit for 90 min", "critical",
                        ["Peak: 20°C at 08:30Z"]),
            ],
            sop_citations         = ["SOP-003 §4.1"],
            recommended_actions   = ["Quarantine shipment."],
            risk_level            = "CRITICAL",
            regulatory_reportable = True,
            shipments_analyzed    = ["SHP-0007"],
        )

    def test_to_dict_roundtrip(self):
        import json
        report = self._make_report()
        d = report.to_dict()
        assert d["risk_level"]            == "CRITICAL"
        assert d["regulatory_reportable"] is True
        assert len(d["findings"])         == 1
        assert d["findings"][0]["severity"] == "critical"
        # JSON serialisable
        json.dumps(d)

    def test_to_markdown_contains_sections(self):
        report = self._make_report()
        md     = report.to_markdown()
        for section in ["ColdChain Investigation Report", "Summary", "Findings",
                        "SOP Citations", "Recommended Actions"]:
            assert section in md, f"Missing section: {section!r}"

    def test_to_markdown_contains_query(self):
        report = self._make_report()
        assert "SHP-0007" in report.to_markdown()


# ── mock investigator tests ───────────────────────────────────────────────────

class TestMockInvestigator:
    def _inv(self):
        from backend.agent.investigator import ColdChainInvestigator
        from backend.agent.tools import _clear_cache
        _clear_cache()
        return ColdChainInvestigator(data_dir=SYNTHETIC, force_mock=True)

    def test_investigate_specific_shipment(self):
        inv  = self._inv()
        data = _load_data()
        exc_sids = {r["shipment_id"] for r in data["temperature_readings"]
                    if r.get("is_excursion")}
        sid    = sorted(exc_sids)[0]
        report = inv.investigate(f"Investigate shipment {sid}")
        assert report.query              != ""
        assert report.summary            != ""
        assert isinstance(report.findings, list)
        assert sid in report.shipments_analyzed

    def test_investigate_fleet_query(self):
        inv    = self._inv()
        report = inv.investigate("Give me a fleet overview of all problem shipments")
        assert report.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert len(report.findings) > 0

    def test_report_has_sop_citations(self):
        inv  = self._inv()
        data = _load_data()
        sid  = sorted({r["shipment_id"] for r in data["temperature_readings"]
                       if r.get("is_excursion")})[0]
        report = inv.investigate(f"Investigate {sid}")
        assert len(report.sop_citations) > 0

    def test_report_has_recommended_actions(self):
        inv    = self._inv()
        report = inv.investigate("Investigate fleet problems")
        assert len(report.recommended_actions) > 0

    def test_unknown_shipment_returns_fallback(self):
        inv    = self._inv()
        report = inv.investigate("Tell me about SHP-9999")
        # No crash; should still return a valid report
        assert report.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_pharma_shipment_flagged_regulatory(self):
        inv  = self._inv()
        data = _load_data()
        # Find a pharma shipment with excursions
        exc_sids = {r["shipment_id"] for r in data["temperature_readings"]
                    if r.get("is_excursion")}
        pharma_exc = [
            s["shipment_id"] for s in data["shipments"]
            if s["shipment_id"] in exc_sids
            and s.get("product_category") == "pharma"
        ]
        if not pharma_exc:
            pytest.skip("No pharma excursion shipments in synthetic data")
        report = inv.investigate(f"Investigate {pharma_exc[0]}")
        assert report.regulatory_reportable is True

    def test_risk_level_critical_for_high_risk_shipment(self):
        inv  = self._inv()
        data = _load_data()
        # Pick the shipment with most excursion readings
        from collections import Counter
        counts = Counter(
            r["shipment_id"] for r in data["temperature_readings"]
            if r.get("is_excursion")
        )
        worst_sid = counts.most_common(1)[0][0]
        report    = inv.investigate(f"Full investigation of {worst_sid}")
        assert report.risk_level in ("HIGH", "CRITICAL")


# ── FastAPI route tests ───────────────────────────────────────────────────────

@pytest.fixture
def test_client():
    from fastapi.testclient import TestClient
    from backend.api.main import app
    # Ensure mock mode regardless of env
    from backend.api import routes as r
    r._investigator = None   # reset singleton
    import os
    os.environ.pop("ANTHROPIC_API_KEY", None)
    return TestClient(app)


class TestAPIRoutes:
    def test_health_ok(self, test_client):
        resp = test_client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"]     == "ok"
        assert body["agent_mode"] == "mock"

    def test_investigate_endpoint(self, test_client):
        resp = test_client.post("/api/v1/investigate", json={
            "query": "fleet overview",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "summary"    in body
        assert "risk_level" in body
        assert "findings"   in body

    def test_investigate_with_shipment_id(self, test_client):
        data = _load_data()
        sid  = sorted({r["shipment_id"] for r in data["temperature_readings"]
                       if r.get("is_excursion")})[0]
        resp = test_client.post("/api/v1/investigate", json={
            "query": f"What happened to shipment {sid}?",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert sid in body["shipments_analyzed"]

    def test_fleet_summary_endpoint(self, test_client):
        resp = test_client.get("/api/v1/fleet/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_shipments"] > 0

    def test_fleet_problems_endpoint(self, test_client):
        resp = test_client.get("/api/v1/fleet/problems?limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) <= 5

    def test_shipment_analysis_endpoint(self, test_client):
        data = _load_data()
        sid  = data["shipments"][0]["shipment_id"]
        resp = test_client.get(f"/api/v1/shipments/{sid}/analysis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["shipment_id"] == sid

    def test_shipment_analysis_404(self, test_client):
        resp = test_client.get("/api/v1/shipments/SHP-9999/analysis")
        assert resp.status_code == 404

    def test_investigate_empty_query_rejected(self, test_client):
        resp = test_client.post("/api/v1/investigate", json={"query": "hi"})
        assert resp.status_code == 422   # Pydantic min_length=5

    def test_fleet_problems_status_filter(self, test_client):
        resp = test_client.get("/api/v1/fleet/problems?status_filter=failed_inspection")
        assert resp.status_code == 200
        for item in resp.json():
            assert item["status"] == "failed_inspection"
