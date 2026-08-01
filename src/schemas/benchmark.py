from typing import Literal

from pydantic import Field, HttpUrl, computed_field

from src.schemas.inference import OutreachOutput, StrictModel


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
