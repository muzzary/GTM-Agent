import json
from pathlib import Path

from src.schemas.benchmark import BaselineReport

MAX_BASELINE_REPORT_BYTES = 5_000_000


class BaselineReportIOError(ValueError):
    """Raised when a baseline report cannot be safely read or written."""


def save_baseline_report(report: BaselineReport, path: Path) -> None:
    payload = json.dumps(
        report.model_dump(
            mode="json",
            exclude={
                "total_cases",
                "valid_output_count",
                "passed_case_count",
                "unsupported_claim_count",
                "unresolved_evidence_count",
                "failure_examples",
            },
        ),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    encoded = payload.encode("utf-8")
    if len(encoded) > MAX_BASELINE_REPORT_BYTES:
        raise BaselineReportIOError("baseline report exceeds the 5 MB size limit")
    try:
        path.write_bytes(encoded)
    except OSError as exc:
        raise BaselineReportIOError(f"unable to write baseline report: {exc}") from exc


def load_baseline_report(path: Path) -> BaselineReport:
    try:
        if path.stat().st_size > MAX_BASELINE_REPORT_BYTES:
            raise BaselineReportIOError(
                "baseline report exceeds the 5 MB size limit"
            )
        raw = json.loads(path.read_text(encoding="utf-8"))
    except BaselineReportIOError:
        raise
    except json.JSONDecodeError as exc:
        raise BaselineReportIOError("baseline report is not valid JSON") from exc
    except OSError as exc:
        raise BaselineReportIOError(f"unable to read baseline report: {exc}") from exc
    if not isinstance(raw, dict):
        raise BaselineReportIOError("baseline report JSON must be an object")
    try:
        return BaselineReport.model_validate(raw)
    except ValueError as exc:
        raise BaselineReportIOError("baseline report failed schema validation") from exc
