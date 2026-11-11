"""
Day 7 — End-to-end tests: 20+ natural-language investigation scenarios.

All run against the mock investigator (no ANTHROPIC_API_KEY required) and
the FastAPI TestClient (no live server required).
Covers: fleet queries, shipment-specific, truck-based, product-category,
regulatory, edge cases, concurrent requests, and API error handling.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SYNTHETIC = ROOT / "data" / "synthetic"


# ── shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def inv():
    from backend.agent.investigator import ColdChainInvestigator
    from backend.agent.tools import _clear_cache
    _clear_cache()
    return ColdChainInvestigator(data_dir=SYNTHETIC, force_mock=True)


@pytest.fixture(scope="module")
def data():
    from backend.agent.tools import _clear_cache, load_synthetic_data
    _clear_cache()
    return load_synthetic_data(SYNTHETIC)


@pytest.fixture(scope="module")
def client():
    import os
    os.environ.pop("ANTHROPIC_API_KEY", None)
    from fastapi.testclient import TestClient
    from backend.api import routes
    from backend.api.main import app
    routes._investigator = None
    return TestClient(app)


# ── helper ────────────────────────────────────────────────────────────────────

def _valid_report(r) -> None:
    """Assert that an InvestigationReport is structurally valid."""
    assert r.query
    assert r.summary
    assert r.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert isinstance(r.findings, list)
    assert isinstance(r.sop_citations, list)
    assert isinstance(r.recommended_actions, list)
    assert isinstance(r.regulatory_reportable, bool)


# ── 1. Fleet-level queries ────────────────────────────────────────────────────

class TestFleetQueries:
    def test_fleet_overview(self, inv):
        r = inv.investigate("Give me a fleet overview of all shipments")
        _valid_report(r)
        assert r.findings

    def test_problem_shipments_query(self, inv):
        r = inv.investigate("Which shipments had temperature excursions?")
        _valid_report(r)

    def test_financial_loss_query(self, inv, data):
        r = inv.investigate("What is the total financial loss from cold-chain incidents?")
        _valid_report(r)
        total = sum(i.get("financial_loss_usd", 0) or 0 for i in data["incidents"])
        # summary or findings should reference the fleet data
        assert r.findings

    def test_maintenance_overdue_query(self, inv, data):
        r = inv.investigate("Which trucks are overdue for maintenance?")
        _valid_report(r)
        overdue = [t["truck_id"] for t in data["trucks"]
                   if t.get("current_status") == "maintenance_required"]
        if overdue:
            combined = (r.summary
                        + " ".join(f.detail for f in r.findings)
                        + " ".join(e for f in r.findings for e in f.evidence))
            assert any(tid in combined for tid in overdue)

    def test_compliance_rate_query(self, inv):
        r = inv.investigate("What percentage of our shipments are non-compliant?")
        _valid_report(r)

    def test_worst_shipments_query(self, inv):
        r = inv.investigate("Show me the worst problem shipments in the fleet")
        _valid_report(r)
        assert r.risk_level in ("MEDIUM", "HIGH", "CRITICAL")

    def test_regulatory_incidents_query(self, inv):
        r = inv.investigate("Are there any incidents that require regulatory reporting?")
        _valid_report(r)


# ── 2. Shipment-specific queries ──────────────────────────────────────────────

class TestShipmentQueries:
    def _worst_excursion_sid(self, data) -> str:
        from collections import Counter
        counts = Counter(
            r["shipment_id"] for r in data["temperature_readings"]
            if r.get("is_excursion")
        )
        return counts.most_common(1)[0][0]

    def test_specific_shipment_investigation(self, inv, data):
        sid = sorted({r["shipment_id"] for r in data["temperature_readings"]
                      if r.get("is_excursion")})[0]
        r = inv.investigate(f"Investigate shipment {sid}")
        _valid_report(r)
        assert sid in r.shipments_analyzed

    def test_worst_excursion_shipment(self, inv, data):
        sid = self._worst_excursion_sid(data)
        r   = inv.investigate(f"Full investigation of {sid} — what caused the temperature excursion?")
        _valid_report(r)
        assert r.risk_level in ("HIGH", "CRITICAL")

    def test_mkt_query(self, inv, data):
        sid = self._worst_excursion_sid(data)
        r   = inv.investigate(f"What is the MKT for shipment {sid} and does it indicate product spoilage?")
        _valid_report(r)
        assert sid in r.shipments_analyzed

    def test_door_event_query(self, inv, data):
        # Find shipment with door events and excursions
        exc_sids = {r["shipment_id"] for r in data["temperature_readings"]
                    if r.get("is_excursion")}
        door_sids = {d["shipment_id"] for d in data["door_events"]}
        overlap   = exc_sids & door_sids
        if not overlap:
            pytest.skip("No shipment with both excursion and door events")
        sid = sorted(overlap)[0]
        r   = inv.investigate(f"Was an unscheduled door opening responsible for the excursion in {sid}?")
        _valid_report(r)

    def test_failed_inspection_shipment(self, inv, data):
        failed_sids = [s["shipment_id"] for s in data["shipments"]
                       if s.get("status") == "failed_inspection"]
        if not failed_sids:
            pytest.skip("No failed-inspection shipments")
        sid = failed_sids[0]
        r   = inv.investigate(f"Why did shipment {sid} fail inspection?")
        _valid_report(r)

    def test_multiple_shipments_in_query(self, inv, data):
        exc_sids = sorted({r["shipment_id"] for r in data["temperature_readings"]
                           if r.get("is_excursion")})[:2]
        r = inv.investigate(f"Compare excursions on {exc_sids[0]} and {exc_sids[1]}")
        _valid_report(r)
        assert exc_sids[0] in r.shipments_analyzed


# ── 3. Truck-based queries ────────────────────────────────────────────────────

class TestTruckQueries:
    def test_truck_incident_history(self, inv, data):
        from collections import Counter
        counts = Counter(i.get("truck_id") for i in data["incidents"] if i.get("truck_id"))
        if not counts:
            pytest.skip("No truck incidents in data")
        tid = counts.most_common(1)[0][0]
        r   = inv.investigate(f"Show me the incident history for truck {tid}")
        _valid_report(r)

    def test_overdue_truck_query(self, inv, data):
        overdue = [t["truck_id"] for t in data["trucks"]
                   if t.get("current_status") == "maintenance_required"]
        if not overdue:
            pytest.skip("No overdue trucks")
        tid = overdue[0]
        r   = inv.investigate(f"What is the maintenance status of {tid}? Is it safe to use?")
        _valid_report(r)

    def test_fleet_truck_risk_query(self, inv):
        r = inv.investigate("Which trucks pose the highest cold-chain risk right now?")
        _valid_report(r)


# ── 4. Product-category queries ───────────────────────────────────────────────

class TestProductCategoryQueries:
    def test_pharma_excursion_query(self, inv, data):
        exc_sids  = {r["shipment_id"] for r in data["temperature_readings"]
                     if r.get("is_excursion")}
        pharma_exc = [s["shipment_id"] for s in data["shipments"]
                      if s["shipment_id"] in exc_sids
                      and s.get("product_category") == "pharma"]
        if not pharma_exc:
            pytest.skip("No pharma excursion shipments")
        r = inv.investigate(f"Investigate pharmaceutical excursion on {pharma_exc[0]} — is regulatory reporting required?")
        _valid_report(r)
        assert r.regulatory_reportable is True

    def test_frozen_product_query(self, inv, data):
        frozen_exc = [
            s["shipment_id"] for s in data["shipments"]
            if s.get("product_category") == "frozen"
            and s["shipment_id"] in {r["shipment_id"] for r in data["temperature_readings"]
                                     if r.get("is_excursion")}
        ]
        if not frozen_exc:
            pytest.skip("No frozen excursion shipments")
        r = inv.investigate(f"Was the frozen product in {frozen_exc[0]} compromised?")
        _valid_report(r)


# ── 5. Recommended-action quality checks ─────────────────────────────────────

class TestReportQuality:
    def test_report_has_min_recommended_actions(self, inv):
        r = inv.investigate("Fleet investigation")
        assert len(r.recommended_actions) >= 2

    def test_report_has_min_sop_citations(self, inv, data):
        sid = sorted({r["shipment_id"] for r in data["temperature_readings"]
                      if r.get("is_excursion")})[0]
        r = inv.investigate(f"Investigate {sid}")
        assert len(r.sop_citations) >= 1

    def test_critical_risk_has_regulatory_flag(self, inv, data):
        """Any CRITICAL-risk report should set regulatory_reportable=True."""
        from collections import Counter
        worst_sid = Counter(
            r["shipment_id"] for r in data["temperature_readings"]
            if r.get("is_excursion")
        ).most_common(1)[0][0]
        r = inv.investigate(f"Full investigation of {worst_sid}")
        if r.risk_level == "CRITICAL":
            assert r.regulatory_reportable is True

    def test_markdown_renders_all_sections(self, inv):
        r  = inv.investigate("fleet overview")
        md = r.to_markdown()
        for section in ["ColdChain Investigation Report", "Summary", "Findings",
                        "SOP Citations", "Recommended Actions"]:
            assert section in md

    def test_report_is_json_serialisable(self, inv):
        import json
        r = inv.investigate("fleet overview")
        json.dumps(r.to_dict())


# ── 6. Edge cases ─────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_unknown_shipment_id(self, inv):
        r = inv.investigate("Investigate shipment SHP-9999")
        _valid_report(r)   # must not crash

    def test_unknown_truck_id(self, inv):
        r = inv.investigate("Investigate truck TRK-999")
        _valid_report(r)

    def test_mixed_case_shipment_id(self, inv, data):
        sid = sorted({r["shipment_id"] for r in data["temperature_readings"]
                      if r.get("is_excursion")})[0]
        r   = inv.investigate(f"Look at {sid.lower()}")
        _valid_report(r)

    def test_very_long_query(self, inv):
        long_q = "What is the status of " + ("shipment SHP-0001 and " * 30) + "the fleet?"
        r = inv.investigate(long_q[:2000])
        _valid_report(r)

    def test_no_entity_query_returns_fleet_view(self, inv):
        r = inv.investigate("Show me everything about cold chain compliance")
        _valid_report(r)
        assert r.findings   # fleet fallback should produce findings

    def test_special_characters_in_query(self, inv):
        r = inv.investigate("What happened? Any excursions > 10°C?")
        _valid_report(r)


# ── 7. Concurrent requests ────────────────────────────────────────────────────

class TestConcurrency:
    def test_concurrent_investigations(self, inv):
        queries = [
            "fleet overview",
            "worst problem shipments",
            "trucks with overdue maintenance",
        ]
        results = [None] * len(queries)
        errors  = []

        def run(i, q):
            try:
                results[i] = inv.investigate(q)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run, args=(i, q)) for i, q in enumerate(queries)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=15)

        assert not errors, f"Concurrent errors: {errors}"
        for r in results:
            assert r is not None
            _valid_report(r)

    def test_concurrent_api_requests(self, client):
        results = [None] * 3
        errors  = []

        def call(i, query):
            try:
                resp = client.post("/api/v1/investigate", json={"query": query})
                results[i] = resp.status_code
            except Exception as e:
                errors.append(e)

        queries = ["fleet overview", "worst shipments", "regulatory incidents"]
        threads = [threading.Thread(target=call, args=(i, q)) for i, q in enumerate(queries)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=15)

        assert not errors
        assert all(c == 200 for c in results), f"Status codes: {results}"


# ── 8. API error handling ─────────────────────────────────────────────────────

class TestAPIErrorHandling:
    def test_query_too_short_rejected(self, client):
        assert client.post("/api/v1/investigate", json={"query": "hi"}).status_code == 422

    def test_missing_query_field_rejected(self, client):
        assert client.post("/api/v1/investigate", json={}).status_code == 422

    def test_invalid_json_rejected(self, client):
        resp = client.post("/api/v1/investigate",
                           content=b"not json",
                           headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_unknown_shipment_404(self, client):
        assert client.get("/api/v1/shipments/SHP-9999/analysis").status_code == 404

    def test_fleet_problems_limit_clamped(self, client):
        resp = client.get("/api/v1/fleet/problems?limit=200")
        # pydantic Query(ge=1, le=100) → 422
        assert resp.status_code == 422

    def test_fleet_problems_bad_limit(self, client):
        assert client.get("/api/v1/fleet/problems?limit=0").status_code == 422

    def test_all_endpoints_respond(self, client):
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/fleet/summary").status_code == 200
        assert client.get("/api/v1/fleet/problems").status_code == 200
        assert client.get("/").status_code == 200
