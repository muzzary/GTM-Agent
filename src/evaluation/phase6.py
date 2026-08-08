from typing import Literal

from pydantic import Field, computed_field

from src.schemas.base import StrictModel
from src.schemas.benchmark import BaselineReport
from src.schemas.inference import GenerationSettings


class AdapterComparisonReport(StrictModel):
    report_version: Literal["1.0"] = "1.0"
    benchmark_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generation: GenerationSettings
    base_model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    adapter_model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    adapter_id: str = Field(min_length=3, max_length=200)
    adapter_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    total_cases: int = Field(gt=0)
    base_valid_output_rate: float = Field(ge=0, le=1)
    adapter_valid_output_rate: float = Field(ge=0, le=1)
    valid_output_rate_delta: float
    base_passed_case_count: int = Field(ge=0)
    adapter_passed_case_count: int = Field(ge=0)
    passed_case_count_delta: int
    adapter_unsupported_claim_count: int = Field(ge=0)
    adapter_unresolved_evidence_count: int = Field(ge=0)
    quality_change: Literal["improved", "regressed", "unchanged"]
    factuality_gates_passed: bool
    no_case_regressions: bool
    regressed_case_ids: list[str] = Field(max_length=50)
    improved_case_ids: list[str] = Field(max_length=50)

    @computed_field
    @property
    def accepted(self) -> bool:
        return self.factuality_gates_passed and self.no_case_regressions


def compare_baseline_reports(
    base: BaselineReport,
    adapter: BaselineReport,
    benchmark_manifest_sha256: str,
) -> AdapterComparisonReport:
    _validate_report_pair(base, adapter)
    base_by_case = {case.case_id: case for case in base.cases}
    adapter_by_case = {case.case_id: case for case in adapter.cases}
    regressed_case_ids = []
    improved_case_ids = []
    for case_id in base_by_case:
        base_score = _case_score(base_by_case[case_id])
        adapter_score = _case_score(adapter_by_case[case_id])
        if adapter_score < base_score:
            regressed_case_ids.append(case_id)
        elif adapter_score > base_score:
            improved_case_ids.append(case_id)

    passed_delta = adapter.passed_case_count - base.passed_case_count
    quality_change = (
        "improved"
        if passed_delta > 0
        else "regressed"
        if passed_delta < 0
        else "unchanged"
    )
    return AdapterComparisonReport(
        benchmark_manifest_sha256=benchmark_manifest_sha256,
        generation=base.generation,
        base_model_revision=base.model.model_revision,
        adapter_model_revision=adapter.model.model_revision,
        adapter_id=adapter.model.adapter_id,
        adapter_revision=adapter.model.adapter_revision,
        total_cases=base.total_cases,
        base_valid_output_rate=base.valid_output_count / base.total_cases,
        adapter_valid_output_rate=adapter.valid_output_count / adapter.total_cases,
        valid_output_rate_delta=(
            adapter.valid_output_count / adapter.total_cases
            - base.valid_output_count / base.total_cases
        ),
        base_passed_case_count=base.passed_case_count,
        adapter_passed_case_count=adapter.passed_case_count,
        passed_case_count_delta=passed_delta,
        adapter_unsupported_claim_count=adapter.unsupported_claim_count,
        adapter_unresolved_evidence_count=adapter.unresolved_evidence_count,
        quality_change=quality_change,
        factuality_gates_passed=(
            adapter.unsupported_claim_count == 0
            and adapter.unresolved_evidence_count == 0
        ),
        no_case_regressions=not regressed_case_ids,
        regressed_case_ids=regressed_case_ids,
        improved_case_ids=improved_case_ids,
    )


def _validate_report_pair(base: BaselineReport, adapter: BaselineReport) -> None:
    if base.generation != adapter.generation:
        raise ValueError("base and adapter generation settings do not match")
    if base.model.model_id != adapter.model.model_id:
        raise ValueError("base and adapter model IDs do not match")
    if base.model.model_revision != adapter.model.model_revision:
        raise ValueError("base model revision does not match adapter base revision")
    if adapter.model.adapter_id is None or adapter.model.adapter_revision is None:
        raise ValueError("adapter report must include adapter identity")
    if [case.case_id for case in base.cases] != [
        case.case_id for case in adapter.cases
    ]:
        raise ValueError("base and adapter benchmark cases do not match")


def _case_score(case: object) -> int:
    return int(
        getattr(case, "output", None) is not None
        and getattr(case, "evaluation", None) is not None
        and getattr(case.evaluation, "passed", False)
    )
