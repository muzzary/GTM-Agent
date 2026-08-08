import json
from pathlib import Path

from src.evaluation.phase6 import AdapterComparisonReport
from src.schemas.training import AdapterArtifactMetadata

MAX_PHASE6_REPORT_BYTES = 5_000_000
MAX_METADATA_BYTES = 100_000


class Phase6ReportIOError(ValueError):
    """Raised when a Phase 6 artifact cannot be safely read or written."""


def save_comparison_report(report: AdapterComparisonReport, path: Path) -> None:
    _write_json(report.model_dump(mode="json", exclude={"accepted"}), path)


def load_comparison_report(path: Path) -> AdapterComparisonReport:
    raw = _read_json(path, MAX_PHASE6_REPORT_BYTES)
    try:
        return AdapterComparisonReport.model_validate(raw)
    except ValueError as exc:
        raise Phase6ReportIOError("comparison report failed schema validation") from exc


def load_adapter_metadata(path: Path) -> AdapterArtifactMetadata:
    raw = _read_json(path, MAX_METADATA_BYTES)
    try:
        return AdapterArtifactMetadata.model_validate(raw)
    except ValueError as exc:
        raise Phase6ReportIOError("adapter metadata failed schema validation") from exc


def _write_json(value: object, path: Path) -> None:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_PHASE6_REPORT_BYTES:
        raise Phase6ReportIOError("Phase 6 report exceeds the 5 MB size limit")
    try:
        path.write_bytes(encoded)
    except OSError as exc:
        raise Phase6ReportIOError(f"unable to write Phase 6 report: {exc}") from exc


def _read_json(path: Path, max_bytes: int) -> object:
    try:
        if path.stat().st_size > max_bytes:
            raise Phase6ReportIOError("Phase 6 artifact exceeds its size limit")
        return json.loads(path.read_text(encoding="utf-8"))
    except Phase6ReportIOError:
        raise
    except json.JSONDecodeError as exc:
        raise Phase6ReportIOError("Phase 6 artifact is not valid JSON") from exc
    except OSError as exc:
        raise Phase6ReportIOError(f"unable to read Phase 6 artifact: {exc}") from exc
