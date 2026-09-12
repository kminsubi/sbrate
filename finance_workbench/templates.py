from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

ALLOWED_OUTPUT_TYPES = {"excel", "word", "powerpoint"}

@dataclass
class FirmTemplateContract:
    template_id: str
    template_name: str
    output_type: str
    required_sections: list[str] = field(default_factory=list)
    required_source_trace: bool = True
    human_approval_required: bool = True
    prohibited_behaviors: list[str] = field(default_factory=lambda: [
        "invent missing figures",
        "drop source references",
        "silently change accounting/finance assumptions",
        "overwrite an approved template without explicit permission",
    ])

    def validate(self) -> None:
        if not self.template_id.strip():
            raise ValueError("template_id is required")
        if not self.template_name.strip():
            raise ValueError("template_name is required")
        if self.output_type not in ALLOWED_OUTPUT_TYPES:
            raise ValueError(f"unsupported output_type: {self.output_type}")
        if not self.required_sections:
            raise ValueError("required_sections cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

def default_excel_model_contract() -> FirmTemplateContract:
    return FirmTemplateContract(
        template_id="finance_excel_model_v1",
        template_name="Finance Analysis Workbook",
        output_type="excel",
        required_sections=["Input","Calculation","Actual","Variance","SourceTrace","Assumptions"],
    )

def default_executive_one_pager_contract() -> FirmTemplateContract:
    return FirmTemplateContract(
        template_id="executive_one_pager_v1",
        template_name="Executive One-Pager",
        output_type="powerpoint",
        required_sections=[
            "Executive conclusion","Key figures","Simulation vs actual","Drivers / causes",
            "Risks","Recommended actions","Source trace / as-of date",
        ],
    )

def default_research_note_contract() -> FirmTemplateContract:
    return FirmTemplateContract(
        template_id="finance_research_note_v1",
        template_name="Finance Research Note",
        output_type="word",
        required_sections=["Question","Executive answer","Evidence","Analysis","Risks / limitations","Source trace"],
    )

def build_output_manifest(
    contract: FirmTemplateContract,
    *,
    analysis_packet_id: str,
    source_count: int,
) -> dict[str, Any]:
    contract.validate()
    if not analysis_packet_id.strip():
        raise ValueError("analysis_packet_id is required")
    if source_count < 1:
        raise ValueError("at least one source is required for financial output")
    return {
        "template": contract.to_dict(),
        "analysis_packet_id": analysis_packet_id,
        "source_count": source_count,
        "render_status": "contract_only",
        "write_policy": "generate a new artifact; never overwrite approved originals automatically",
    }
