"""Evidence-first finance analysis contracts for SBRateBot."""

from .evidence import (
    EvidenceItem,
    SourceLocator,
    build_rate_evidence,
    build_rate_change_packet,
)
from .analysis import (
    CalculationStep,
    Claim,
    FinanceAnalysisPacket,
    build_scaled_benchmark,
)
from .templates import (
    FirmTemplateContract,
    default_excel_model_contract,
    default_executive_one_pager_contract,
)

__all__ = [
    "EvidenceItem",
    "SourceLocator",
    "build_rate_evidence",
    "build_rate_change_packet",
    "CalculationStep",
    "Claim",
    "FinanceAnalysisPacket",
    "build_scaled_benchmark",
    "FirmTemplateContract",
    "default_excel_model_contract",
    "default_executive_one_pager_contract",
]
