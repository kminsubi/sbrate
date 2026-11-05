from __future__ import annotations

import unittest

from finance_workbench.analysis import (
    FinanceAnalysisPacket,
    build_claim,
    build_scaled_benchmark,
)
from finance_workbench.evidence import build_rate_change_packet, build_rate_evidence
from finance_workbench.templates import (
    build_output_manifest,
    default_excel_model_contract,
    default_executive_one_pager_contract,
)


class FinanceWorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.current = {
            "bank": "테스트저축은행",
            "product": "정기예금",
            "top_12m": "3.70",
            "base_12m": "3.60",
            "reg_date": "2026-09-10 00:00:00",
            "url": "https://example.com/product",
        }
        self.previous = {
            "bank": "테스트저축은행",
            "product": "정기예금",
            "top_12m": "3.50",
            "base_12m": "3.40",
            "reg_date": "2026-09-09 00:00:00",
            "url": "https://example.com/product",
        }

    def test_rate_evidence_preserves_source_locator(self) -> None:
        item = build_rate_evidence(
            self.current,
            term_months=12,
            snapshot_updated_at="2026-09-10 18:39:11",
        )
        self.assertEqual(item.value, "3.70")
        self.assertEqual(item.locator.source_file, "data/latest_rates.json")
        self.assertIn("top_12m", item.locator.field_path)
        self.assertEqual(item.locator.source_url, "https://example.com/product")

    def test_rate_change_is_traceable_to_two_snapshots(self) -> None:
        packet = build_rate_change_packet(
            self.current,
            self.previous,
            term_months=12,
        )
        self.assertEqual(packet["calculation"]["result"], "0.20")
        self.assertEqual(packet["calculation"]["direction"], "rise")
        self.assertEqual(len(packet["calculation"]["input_evidence_ids"]), 2)

    def test_scaled_benchmark_matches_actual_opb_ratio(self) -> None:
        result = build_scaled_benchmark(
            simulated_opb="750.8",
            actual_opb="317.1",
            simulated_values_by_period={"1Y": "100", "2Y": "80"},
        )
        self.assertEqual(result["scale_ratio"], "0.4223")
        self.assertEqual(result["scaled_values_by_period"]["1Y"], "42.23")
        self.assertIn("비례환산", result["required_caveat"])

    def test_financial_claim_requires_trace(self) -> None:
        with self.assertRaises(ValueError):
            build_claim("근거 없는 결론")

    def test_packet_rejects_untraceable_claim(self) -> None:
        evidence = build_rate_evidence(self.current)
        claim = build_claim(
            "12개월 최고금리는 3.70%입니다.",
            evidence_ids=[evidence.evidence_id],
        )
        packet = FinanceAnalysisPacket(
            title="금리 분석",
            as_of="2026-09-10",
            evidence=[evidence.to_dict()],
            claims=[claim],
        )
        payload = packet.to_dict()
        self.assertTrue(payload["human_approval_required"])
        self.assertTrue(payload["claims"][0]["traceable"])

    def test_firm_template_contracts_force_source_trace(self) -> None:
        excel = default_excel_model_contract()
        ppt = default_executive_one_pager_contract()
        self.assertTrue(excel.required_source_trace)
        self.assertIn("SourceTrace", excel.required_sections)
        self.assertTrue(ppt.human_approval_required)
        manifest = build_output_manifest(
            excel,
            analysis_packet_id="packet-1",
            source_count=2,
        )
        self.assertEqual(manifest["render_status"], "contract_only")


if __name__ == "__main__":
    unittest.main()
