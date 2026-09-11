from __future__ import annotations

import unittest
from unittest.mock import patch

import management_executive_matrix as mx


BANKS = [
    ("우리금융저축은행", 1000, 700, 400, 300),
    ("신한저축은행", 1200, 800, 450, 350),
    ("하나저축은행", 900, 650, 380, 270),
    ("KB저축은행", 1100, 750, 420, 330),
]


def _store():
    def rows(scale=1.0):
        return [
            {
                "bank": bank,
                "total_assets": assets * scale,
                "total_loans": loans * scale,
                "corporate_loans": corp * scale,
                "household_loans": hh * scale,
            }
            for bank, assets, loans, corp, hh in BANKS
        ]
    return {
        "updated_at": "2026-09-11 09:00:00",
        "quarters": {
            "2026Q2": {"label": "2026년 2분기", "as_of": "2026-06-30", "banks": rows()},
            "2025Q4": {"label": "2025년 4분기", "as_of": "2025-12-31", "banks": rows(.9)},
        },
    }


def _intel(section, base=None, compare=None):
    values = {
        "우리금융저축은행": {
            "funding": [950, 760, 80, 73.68, 18, 14],
            "profitability": [25, 20, 40, 75, 60, 35],
            "soundness": [14, 110, 4.2, 5.1, 120, 45],
        },
        "신한저축은행": {
            "funding": [1100, 800, 72.7, 72.73, 20, 15],
            "profitability": [30, 24, 44, 82, 67, 38],
            "soundness": [13, 105, 4.8, 5.5, 115, 48],
        },
        "하나저축은행": {
            "funding": [850, 690, 81.2, 76.47, 16, 12],
            "profitability": [18, 15, 31, 66, 51, 35],
            "soundness": [15, 115, 3.7, 4.6, 130, 43],
        },
        "KB저축은행": {
            "funding": [1000, 770, 77, 75, 19, 14],
            "profitability": [27, 22, 42, 79, 63, 37],
            "soundness": [12.5, 100, 5.0, 5.9, 100, 50],
        },
    }
    keys = {
        "funding": [
            "deposits", "time_deposits", "time_deposit_mix",
            "simple_loan_deposit_ratio", "deposit_interest_expense",
            "time_deposit_interest_expense",
        ],
        "profitability": [
            "operating_profit", "net_income", "net_interest_income",
            "interest_income", "loan_interest_income", "interest_expense",
        ],
        "soundness": [
            "bis_ratio", "liquidity_ratio", "delinquency_ratio",
            "npl_ratio_effective", "npl_coverage_ratio", "allowance_balance",
        ],
    }[section]
    rows = []
    for bank, _, _, _, _ in BANKS:
        metrics = {}
        for key, value in zip(keys, values[bank][section]):
            metrics[key] = {
                "base": value,
                "compare": value - 1,
                "delta": 1,
                "yoy_compare": value - 2,
                "yoy_delta": 2,
            }
        rows.append({"bank": bank, "metrics": metrics})
    return {
        "ok": True,
        "ready": True,
        "base": "2026Q2",
        "base_label": "2026년 2분기",
        "updated_at": "2026-09-11 09:00:00",
        "rows": rows,
        "notes": {"roa_roe_basis": "ROA·ROE는 현재 분기 직접 산출하지 않음"},
    }


class ExecutiveMatrixTests(unittest.TestCase):
    @patch("management_executive_matrix.mr._load_store", side_effect=_store)
    @patch("management_executive_matrix.mi.build_intelligence", side_effect=_intel)
    def test_builds_four_peer_matrix(self, _intel_mock, _store_mock):
        data = mx.build_executive_matrix("2026Q2")
        self.assertTrue(data["ok"])
        self.assertTrue(data["ready"])
        self.assertEqual([x["id"] for x in data["peers"]], ["woori", "shinhan", "hana", "kb"])
        self.assertGreater(len(data["rows"]), 15)
        self.assertGreater(data["coverage"]["ratio"], 0.9)

    @patch("management_executive_matrix.mr._load_store", side_effect=_store)
    @patch("management_executive_matrix.mi.build_intelligence", side_effect=_intel)
    def test_lower_is_better_ranking_is_respected(self, _intel_mock, _store_mock):
        data = mx.build_executive_matrix("2026Q2")
        delinquency = next(row for row in data["rows"] if row["key"] == "delinquency_ratio")
        self.assertEqual(delinquency["ranks"]["hana"], 1)
        self.assertEqual(delinquency["ranks"]["kb"], 4)

    @patch("management_executive_matrix.mr._load_store", side_effect=_store)
    @patch("management_executive_matrix.mi.build_intelligence", side_effect=_intel)
    def test_unverified_phase2_metrics_are_not_fabricated(self, _intel_mock, _store_mock):
        data = mx.build_executive_matrix("2026Q2")
        keys = {row["key"] for row in data["rows"]}
        self.assertIn("loan_interest_income", keys)
        self.assertNotIn("loan_interest_yield", keys)
        self.assertIn("대출이자수익률", data["phase2_pending"])
        verified = data["phase2_verified_source_map"]
        self.assertEqual(verified["loan_receivable_trading_gain"]["account"], "A40")
        self.assertEqual(verified["loan_receivable_trading_loss"]["account"], "B530")
        self.assertEqual(verified["borrowing_interest_expense"]["account"], "A22")
        self.assertIn("대출평잔", data["phase2_policy"])


if __name__ == "__main__":
    unittest.main()
