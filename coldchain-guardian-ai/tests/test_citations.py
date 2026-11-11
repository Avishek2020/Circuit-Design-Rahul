"""
Day 7 — Citation integrity tests.

Verifies that:
1. All SOP PDF files are present and readable
2. Mock-investigator citations follow the correct format (SOP-00X §N)
3. SOP numbers cited are from the valid set {001, 002, 003, 004}
4. Section numbers cited actually exist in the SOP documents
5. Anthropic tool schemas are well-formed
6. submit_investigation_report schema has all required fields
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT     = Path(__file__).resolve().parent.parent
SOP_DIR  = ROOT / "data" / "raw" / "sop_documents"
SYNTHETIC = ROOT / "data" / "synthetic"

sys.path.insert(0, str(ROOT))

# ── SOP section catalogue (extracted from PDFs) ───────────────────────────────

VALID_SOP_SECTIONS: dict[str, set[str]] = {
    "001": {"1","2","3","4","5","5.1","5.2","6","6.1","6.2","6.3","7"},
    "002": {"1","2","3","3.1","3.2","4","5","5.1","6","7"},
    "003": {"1","2","2.1","2.2","3","4","5","6"},
    "004": {"1","2","3","3.1","3.2","4","4.1","5","6","7"},
}

CITATION_RE = re.compile(r"SOP-(\d{3})\s*§([\d.]+)")


def _parse_citation(citation: str) -> tuple[str, str] | None:
    """Return (sop_num, section) or None if pattern doesn't match."""
    m = CITATION_RE.search(citation)
    return (m.group(1), m.group(2)) if m else None


# ── 1. SOP file existence ─────────────────────────────────────────────────────

class TestSOPFilesExist:
    def test_all_four_sop_pdfs_present(self):
        for n in ("001", "002", "003", "004"):
            matches = list(SOP_DIR.glob(f"SOP-{n}*.pdf"))
            assert matches, f"SOP-{n} PDF not found in {SOP_DIR}"

    def test_sop_pdfs_are_non_empty(self):
        for pdf in SOP_DIR.glob("*.pdf"):
            assert pdf.stat().st_size > 1024, f"{pdf.name} is suspiciously small"

    def test_sop_pdfs_text_extractable(self):
        import pymupdf
        for pdf in SOP_DIR.glob("*.pdf"):
            doc  = pymupdf.open(str(pdf))
            text = "".join(p.get_text() for p in doc)
            assert len(text) > 200, f"{pdf.name}: too little text extracted"

    def test_sop_pdfs_have_expected_sections(self):
        import pymupdf
        for pdf in SOP_DIR.glob("*.pdf"):
            num  = re.search(r"SOP-(\d{3})", pdf.stem).group(1)
            doc  = pymupdf.open(str(pdf))
            text = "".join(p.get_text() for p in doc)
            # Every SOP must have a "Purpose" section
            assert "Purpose" in text, f"{pdf.name}: no Purpose section found"


# ── 2. Citation format tests ──────────────────────────────────────────────────

class TestCitationFormat:
    @pytest.fixture(autouse=True)
    def inv(self):
        from backend.agent.investigator import ColdChainInvestigator
        from backend.agent.tools import _clear_cache
        _clear_cache()
        return ColdChainInvestigator(data_dir=SYNTHETIC, force_mock=True)

    def _get_all_citations(self, inv) -> list[str]:
        queries = [
            "fleet overview",
            "worst problem shipments",
        ]
        all_cits: list[str] = []
        for q in queries:
            r = inv.investigate(q)
            all_cits.extend(r.sop_citations)
        return all_cits

    def test_citations_are_non_empty_strings(self, inv):
        for c in self._get_all_citations(inv):
            assert isinstance(c, str)
            assert len(c) > 5

    def test_citations_reference_valid_sop_numbers(self, inv):
        for c in self._get_all_citations(inv):
            parsed = _parse_citation(c)
            if parsed is not None:
                sop_num, _ = parsed
                assert sop_num in VALID_SOP_SECTIONS, \
                    f"Citation references unknown SOP-{sop_num}: {c!r}"

    def test_citations_reference_valid_sections(self, inv):
        for c in self._get_all_citations(inv):
            parsed = _parse_citation(c)
            if parsed is not None:
                sop_num, section = parsed
                valid = VALID_SOP_SECTIONS.get(sop_num, set())
                assert section in valid, \
                    f"Section §{section} not found in SOP-{sop_num}. " \
                    f"Valid sections: {sorted(valid)}"

    def test_citations_follow_sop_section_format(self, inv):
        """Every citation that starts with 'SOP-' must match SOP-00X §N pattern."""
        for c in self._get_all_citations(inv):
            if c.startswith("SOP-"):
                assert CITATION_RE.search(c), \
                    f"Citation does not match SOP-00X §N pattern: {c!r}"

    def test_specific_shipment_investigation_cites_sop003(self, inv):
        """Shipment investigations should cite SOP-003 (temp monitoring) or SOP-002 (breach)."""
        from backend.agent.tools import load_synthetic_data, _clear_cache
        _clear_cache()
        data    = load_synthetic_data(SYNTHETIC)
        exc_sid = sorted({r["shipment_id"] for r in data["temperature_readings"]
                          if r.get("is_excursion")})[0]
        r       = inv.investigate(f"Investigate {exc_sid}")
        cited_sops = {_parse_citation(c)[0] for c in r.sop_citations
                      if _parse_citation(c)}
        assert cited_sops & {"002", "003", "004"}, \
            f"Excursion investigation should cite SOP-002/003/004, got: {r.sop_citations}"


# ── 3. Tool schema validation ─────────────────────────────────────────────────

class TestToolSchemas:
    @pytest.fixture
    def schemas(self):
        from backend.agent.tools import TOOL_SCHEMAS
        return TOOL_SCHEMAS

    def test_all_five_tools_defined(self, schemas):
        names = {t["name"] for t in schemas}
        expected = {
            "get_shipment_analysis",
            "get_fleet_summary",
            "list_problem_shipments",
            "search_sop_documents",
            "submit_investigation_report",
        }
        assert names == expected

    def test_every_tool_has_required_anthropic_fields(self, schemas):
        for tool in schemas:
            assert "name"         in tool, f"{tool.get('name')}: missing 'name'"
            assert "description"  in tool, f"{tool.get('name')}: missing 'description'"
            assert "input_schema" in tool, f"{tool.get('name')}: missing 'input_schema'"
            schema = tool["input_schema"]
            assert schema.get("type") == "object", f"{tool['name']}: input_schema type must be 'object'"

    def test_submit_report_has_all_required_fields(self, schemas):
        submit = next(t for t in schemas if t["name"] == "submit_investigation_report")
        required = set(submit["input_schema"]["required"])
        expected = {"summary", "findings", "recommended_actions", "risk_level", "regulatory_reportable"}
        assert expected <= required, f"Missing required fields: {expected - required}"

    def test_submit_report_risk_level_enum(self, schemas):
        submit    = next(t for t in schemas if t["name"] == "submit_investigation_report")
        risk_prop = submit["input_schema"]["properties"]["risk_level"]
        assert risk_prop.get("enum") == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_submit_report_findings_is_array(self, schemas):
        submit   = next(t for t in schemas if t["name"] == "submit_investigation_report")
        findings = submit["input_schema"]["properties"]["findings"]
        assert findings["type"] == "array"

    def test_all_tool_descriptions_are_non_trivial(self, schemas):
        for tool in schemas:
            assert len(tool["description"]) >= 20, \
                f"{tool['name']}: description too short"

    def test_tools_are_json_serialisable(self, schemas):
        import json
        json.dumps(schemas)   # must not raise


# ── 4. InvestigationReport schema completeness ────────────────────────────────

class TestReportSchema:
    def test_all_dict_keys_present(self):
        from backend.agent.report import Finding, InvestigationReport
        r = InvestigationReport(
            query="test", summary="s",
            findings=[Finding("T", "D", "low")],
            sop_citations=["SOP-001 §1"], recommended_actions=["Do X"],
            risk_level="LOW", regulatory_reportable=False,
            shipments_analyzed=["SHP-0001"],
        )
        d = r.to_dict()
        for key in [
            "query", "summary", "findings", "sop_citations",
            "recommended_actions", "risk_level", "regulatory_reportable",
            "shipments_analyzed", "generated_at",
        ]:
            assert key in d, f"Missing key: {key}"

    def test_finding_severity_enum(self):
        from backend.agent.report import Finding
        for sev in ("low", "medium", "high", "critical"):
            f = Finding("T", "D", sev)
            assert f.severity == sev
