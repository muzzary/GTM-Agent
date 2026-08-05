from typing import Literal

from pydantic import Field, HttpUrl, computed_field, model_validator

from src.schemas.base import StrictModel
from src.schemas.inference import (
    GenerationSettings,
    ModelIdentity,
    OutreachOutput,
)


class CandidateConfig(StrictModel):
    model_id: str = Field(min_length=3, max_length=200)
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    license: Literal["Apache-2.0", "MIT"]
    license_url: HttpUrl
    trust_remote_code: bool = False


class BenchmarkGeneration(StrictModel):
    seed: int = Field(ge=0, le=2**32 - 1)
    do_sample: Literal[False] = False
    max_new_tokens: int = Field(ge=1, le=1024)
    warmup_runs: int = Field(ge=0, le=10)
    measured_runs: int = Field(ge=1, le=10)


class ApprovedClaim(StrictModel):
    claim_id: str = Field(pattern=r"^claim-[a-z0-9-]{3,64}$")
    text: str = Field(min_length=1, max_length=500)


class BenchmarkCase(StrictModel):
    case_id: str = Field(pattern=r"^case-[a-z0-9-]{3,64}$")
    product_category: str = Field(min_length=3, max_length=80)
    icp_pattern: str = Field(min_length=3, max_length=80)
    product_name: str = Field(min_length=1, max_length=120)
    product_description: str = Field(min_length=1, max_length=1000)
    approved_claims: list[ApprovedClaim] = Field(min_length=1, max_length=12)
    prospect_name: str = Field(min_length=1, max_length=120)
    prospect_evidence: list[str] = Field(min_length=1, max_length=12)
    target_role: str = Field(min_length=1, max_length=120)
    pain_hypothesis: str = Field(min_length=1, max_length=500)

    @computed_field
    @property
    def approved_claim_ids(self) -> frozenset[str]:
        return frozenset(claim.claim_id for claim in self.approved_claims)


class HardGates(StrictModel):
    minimum_valid_output_rate: float = Field(ge=0, le=1)
    maximum_unsupported_claim_count: Literal[0] = 0
    require_qlora_smoke: Literal[True] = True


class HumanRubric(StrictModel):
    scale_min: Literal[1] = 1
    scale_max: Literal[5] = 5
    dimensions: list[str] = Field(min_length=1, max_length=12)


class BenchmarkManifest(StrictModel):
    manifest_version: Literal["1.0"] = "1.0"
    candidates: list[CandidateConfig] = Field(min_length=2, max_length=4)
    generation: BenchmarkGeneration
    hard_gates: HardGates
    human_rubric: HumanRubric
    cases: list[BenchmarkCase] = Field(min_length=1, max_length=50)


class CaseEvaluation(StrictModel):
    unsupported_claims: list[str]
    passes_claim_gate: bool


class BaselineCaseEvaluation(StrictModel):
    case_id: str = Field(pattern=r"^case-[a-z0-9-]{3,64}$")
    passed: bool
    unsupported_claims: list[str] = Field(max_length=64)
    unresolved_evidence: list[str] = Field(max_length=64)
    supported_claim_count: int = Field(ge=0, le=64)
    cited_evidence_count: int = Field(ge=0, le=64)


class BaselineCaseResult(StrictModel):
    case_id: str = Field(pattern=r"^case-[a-z0-9-]{3,64}$")
    request_id: str = Field(pattern=r"^req_[a-z0-9]{12,64}$")
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output: OutreachOutput | None = None
    evaluation: BaselineCaseEvaluation | None = None
    retry_count: int = Field(ge=0, le=1)
    failure: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def evaluation_must_match_case(self) -> "BaselineCaseResult":
        if self.evaluation is not None and self.evaluation.case_id != self.case_id:
            raise ValueError("baseline evaluation must match its case")
        if (self.output is None) == (self.failure is None):
            raise ValueError("baseline case must have either output or failure")
        if self.output is not None and self.evaluation is None:
            raise ValueError("successful baseline case requires an evaluation")
        return self


class BaselineTraceEntry(StrictModel):
    case_id: str = Field(pattern=r"^case-[a-z0-9-]{3,64}$")
    request_id: str = Field(pattern=r"^req_[a-z0-9]{12,64}$")
    attempt: int = Field(ge=1, le=2)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_claim_ids: list[str] = Field(max_length=64)
    evidence_ids: list[str] = Field(max_length=64)
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    status: Literal["succeeded", "failed"]
    latency_ms: float | None = Field(default=None, ge=0, le=86_400_000)
    error: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def status_fields_must_match(self) -> "BaselineTraceEntry":
        if self.status == "succeeded" and self.latency_ms is None:
            raise ValueError("successful baseline trace requires latency")
        if self.status == "failed" and self.error is None:
            raise ValueError("failed baseline trace requires an error")
        return self


class BaselineReport(StrictModel):
    report_version: Literal["1.0"] = "1.0"
    manifest_version: Literal["1.0"]
    model: ModelIdentity
    generation: GenerationSettings
    cases: list[BaselineCaseResult] = Field(min_length=1, max_length=50)
    trace: list[BaselineTraceEntry] = Field(min_length=1, max_length=100)

    @computed_field
    @property
    def total_cases(self) -> int:
        return len(self.cases)

    @computed_field
    @property
    def valid_output_count(self) -> int:
        return sum(case.output is not None for case in self.cases)

    @computed_field
    @property
    def passed_case_count(self) -> int:
        return sum(
            case.evaluation is not None and case.evaluation.passed
            for case in self.cases
        )

    @computed_field
    @property
    def unsupported_claim_count(self) -> int:
        return sum(
            len(case.evaluation.unsupported_claims)
            for case in self.cases
            if case.evaluation is not None
        )

    @computed_field
    @property
    def unresolved_evidence_count(self) -> int:
        return sum(
            len(case.evaluation.unresolved_evidence)
            for case in self.cases
            if case.evaluation is not None
        )

    @computed_field
    @property
    def failure_examples(self) -> list[str]:
        return [
            case.case_id
            for case in self.cases
            if case.failure is not None
            or (case.evaluation is not None and not case.evaluation.passed)
        ]


class CandidateResult(StrictModel):
    model_id: str = Field(min_length=3, max_length=200)
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    total_outputs: int = Field(gt=0)
    valid_outputs: int = Field(ge=0)
    unsupported_claim_count: int = Field(ge=0)
    qlora_smoke_passed: bool
    human_rubric_average: float = Field(ge=1, le=5)
    peak_gpu_memory_mb: int = Field(gt=0)
    median_latency_ms: float = Field(ge=0)

    @computed_field
    @property
    def valid_output_rate(self) -> float:
        return self.valid_outputs / self.total_outputs


def output_contract_schema() -> dict[str, object]:
    return OutreachOutput.model_json_schema()
