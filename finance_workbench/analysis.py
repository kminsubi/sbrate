from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from typing import Any, Iterable

def _d(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid numeric value: {value!r}") from exc

def _id(prefix: str, payload: str) -> str:
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:16]}"

@dataclass(frozen=True)
class CalculationStep:
    calculation_id: str
    name: str
    formula: str
    inputs: dict[str, str]
    result: str
    unit: str
    assumptions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class Claim:
    claim_id: str
    statement: str
    evidence_ids: tuple[str, ...] = ()
    calculation_ids: tuple[str, ...] = ()
    caveat: str = ""

    @property
    def traceable(self) -> bool:
        return bool(self.evidence_ids or self.calculation_ids)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["traceable"] = self.traceable
        return data

@dataclass
class FinanceAnalysisPacket:
    title: str
    as_of: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    calculations: list[CalculationStep] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    human_approval_required: bool = True

    def validate(self) -> None:
        if not self.title.strip():
            raise ValueError("title is required")
        if not self.as_of.strip():
            raise ValueError("as_of is required")
        untraceable = [claim.claim_id for claim in self.claims if not claim.traceable]
        if untraceable:
            raise ValueError(f"untraceable claims are not allowed: {untraceable}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "title": self.title,
            "as_of": self.as_of,
            "evidence": self.evidence,
            "calculations": [x.to_dict() for x in self.calculations],
            "claims": [x.to_dict() for x in self.claims],
            "caveats": self.caveats,
            "human_approval_required": self.human_approval_required,
        }

def build_scaled_benchmark(
    *,
    simulated_opb: Any,
    actual_opb: Any,
    simulated_values_by_period: dict[str, Any],
    unit: str = "억원",
    rounding: str = "0.01",
) -> dict[str, Any]:
    sim = _d(simulated_opb)
    actual = _d(actual_opb)
    if sim <= 0:
        raise ValueError("simulated_opb must be positive")
    if actual < 0:
        raise ValueError("actual_opb cannot be negative")
    ratio = actual / sim
    quant = Decimal(rounding)
    scaled: dict[str, str] = {}
    steps: list[CalculationStep] = []
    ratio_id = _id("calc", f"scale_ratio|{sim}|{actual}")
    steps.append(CalculationStep(
        calculation_id=ratio_id,
        name="OPB scale ratio",
        formula="actual_opb / simulated_opb",
        inputs={"actual_opb": str(actual), "simulated_opb": str(sim)},
        result=str(ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        unit="ratio",
        assumptions=("The simulation is scaled proportionally to actual OPB for benchmark comparison.",),
    ))
    for period, value in simulated_values_by_period.items():
        raw = _d(value)
        result = (raw * ratio).quantize(quant, rounding=ROUND_HALF_UP)
        scaled[str(period)] = str(result)
        steps.append(CalculationStep(
            calculation_id=_id("calc", f"{period}|{raw}|{ratio}"),
            name=f"Scaled benchmark: {period}",
            formula="simulated_value * scale_ratio",
            inputs={"simulated_value": str(raw), "scale_ratio_calculation_id": ratio_id},
            result=str(result),
            unit=unit,
            assumptions=("Proportional scaling is a comparison benchmark, not a forecast guarantee.",),
        ))
    return {
        "simulated_opb": str(sim),
        "actual_opb": str(actual),
        "scale_ratio": str(ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "scaled_values_by_period": scaled,
        "calculations": [step.to_dict() for step in steps],
        "required_caveat": (
            "OPB 비례환산은 동일 구성·상환패턴을 가정한 비교 기준이며, 실제 현금흐름의 "
            "상품구성·조기상환·연체·수수료 차이는 별도 분석해야 합니다."
        ),
    }

def build_claim(
    statement: str,
    *,
    evidence_ids: Iterable[str] = (),
    calculation_ids: Iterable[str] = (),
    caveat: str = "",
) -> Claim:
    statement = statement.strip()
    if not statement:
        raise ValueError("claim statement is required")
    eids = tuple(str(x) for x in evidence_ids if str(x))
    cids = tuple(str(x) for x in calculation_ids if str(x))
    claim = Claim(
        claim_id=_id("claim", statement + "|" + "|".join(eids + cids)),
        statement=statement,
        evidence_ids=eids,
        calculation_ids=cids,
        caveat=caveat.strip(),
    )
    if not claim.traceable:
        raise ValueError("financial claims must cite evidence or calculations")
    return claim
