from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any

SUPPORTED_TERMS = (1, 3, 6, 12, 24, 36)

def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        raise ValueError("numeric evidence value is missing")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid numeric evidence value: {value!r}") from exc

def _stable_id(prefix: str, parts: list[str]) -> str:
    payload = "|".join(parts).encode("utf-8")
    return f"{prefix}_{sha256(payload).hexdigest()[:16]}"

@dataclass(frozen=True)
class SourceLocator:
    source_kind: str
    source_file: str
    source_url: str
    as_of: str
    record_key: str
    field_path: str
    original_value: str
    unit: str
    source_note: str = ""

    def validate(self) -> None:
        if not self.source_kind.strip():
            raise ValueError("source_kind is required")
        if not self.source_file.strip() and not self.source_url.strip():
            raise ValueError("source_file or source_url is required")
        if not self.record_key.strip():
            raise ValueError("record_key is required")
        if not self.field_path.strip():
            raise ValueError("field_path is required")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    metric_name: str
    value: str
    unit: str
    locator: SourceLocator
    bank: str = ""
    product: str = ""
    term_months: int | None = None

    def validate(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id is required")
        if not self.metric_name.strip():
            raise ValueError("metric_name is required")
        self.locator.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        data = asdict(self)
        data["locator"] = self.locator.to_dict()
        return data

def _record_key(row: dict[str, Any]) -> str:
    return "|".join([
        str(row.get("bank", "")).strip(),
        str(row.get("product", "")).strip(),
        str(row.get("reg_date", "")).strip(),
    ])

def build_rate_evidence(
    row: dict[str, Any],
    *,
    term_months: int = 12,
    rate_type: str = "top",
    snapshot_file: str = "data/latest_rates.json",
    snapshot_updated_at: str = "",
) -> EvidenceItem:
    if term_months not in SUPPORTED_TERMS:
        raise ValueError(f"unsupported term: {term_months}")
    if rate_type not in {"top", "base"}:
        raise ValueError("rate_type must be 'top' or 'base'")
    field = f"{rate_type}_{term_months}m"
    raw = row.get(field)
    value = _decimal(raw)
    bank = str(row.get("bank", "")).strip()
    product = str(row.get("product", "")).strip()
    key = _record_key(row)
    source_url = str(row.get("url", "")).strip()
    as_of = snapshot_updated_at or str(row.get("reg_date", "")).strip()
    locator = SourceLocator(
        source_kind="sbrate_snapshot",
        source_file=snapshot_file,
        source_url=source_url,
        as_of=as_of,
        record_key=key,
        field_path=f"$[bank={bank!r},product={product!r}].{field}",
        original_value=str(raw),
        unit="% p.a.",
        source_note="Savings-bank deposit-rate snapshot; retain product URL for source verification.",
    )
    evidence_id = _stable_id("ev", [snapshot_file, as_of, key, field, str(value)])
    item = EvidenceItem(
        evidence_id=evidence_id,
        metric_name=f"{rate_type}_rate_{term_months}m",
        value=str(value),
        unit="% p.a.",
        locator=locator,
        bank=bank,
        product=product,
        term_months=term_months,
    )
    item.validate()
    return item

def build_rate_change_packet(
    current_row: dict[str, Any],
    previous_row: dict[str, Any],
    *,
    term_months: int = 12,
    rate_type: str = "top",
    current_snapshot_at: str = "",
    previous_snapshot_at: str = "",
) -> dict[str, Any]:
    current = build_rate_evidence(
        current_row,
        term_months=term_months,
        rate_type=rate_type,
        snapshot_file="data/latest_rates.json",
        snapshot_updated_at=current_snapshot_at,
    )
    previous = build_rate_evidence(
        previous_row,
        term_months=term_months,
        rate_type=rate_type,
        snapshot_file="data/previous_rates.json",
        snapshot_updated_at=previous_snapshot_at,
    )
    cur = _decimal(current.value)
    prev = _decimal(previous.value)
    delta = cur - prev
    direction = "rise" if delta > 0 else "fall" if delta < 0 else "flat"
    return {
        "bank": current.bank,
        "product": current.product,
        "term_months": term_months,
        "rate_type": rate_type,
        "current": current.to_dict(),
        "previous": previous.to_dict(),
        "calculation": {
            "formula": "current_rate - previous_rate",
            "input_evidence_ids": [current.evidence_id, previous.evidence_id],
            "result": str(delta),
            "unit": "%p",
            "direction": direction,
        },
    }
