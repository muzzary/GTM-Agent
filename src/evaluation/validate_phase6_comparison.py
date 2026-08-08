import argparse
import hashlib
import json
from pathlib import Path

from src.evaluation.phase1 import load_manifest
from src.evaluation.phase5_io import load_baseline_report
from src.evaluation.phase6 import compare_baseline_reports
from src.evaluation.phase6_io import load_adapter_metadata, save_comparison_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a Phase 6 base-versus-adapter comparison."
    )
    parser.add_argument("base_report", type=Path)
    parser.add_argument("adapter_report", type=Path)
    parser.add_argument("adapter_metadata", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    base_report = load_baseline_report(args.base_report)
    adapter_report = load_baseline_report(args.adapter_report)
    metadata = load_adapter_metadata(args.adapter_metadata)
    comparison = compare_baseline_reports(
        base_report,
        adapter_report,
        hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        minimum_valid_output_rate=manifest.hard_gates.minimum_valid_output_rate,
    )
    if metadata.adapter_id != comparison.adapter_id:
        raise ValueError("adapter metadata ID does not match comparison")
    if metadata.adapter_revision != comparison.adapter_revision:
        raise ValueError("adapter metadata hash does not match comparison")
    if metadata.base_model_id != adapter_report.model.model_id:
        raise ValueError("adapter metadata base model does not match report")
    if metadata.base_model_revision != comparison.adapter_model_revision:
        raise ValueError("adapter metadata base revision does not match report")
    if metadata.dataset_id != "dataset-phase6-pilot":
        raise ValueError("adapter metadata dataset is not the reviewed Phase 6 pilot")
    save_comparison_report(comparison, args.output)
    print(
        json.dumps(
            {
                "manifest_version": manifest.manifest_version,
                "quality_change": comparison.quality_change,
                "valid_output_gate_passed": comparison.valid_output_gate_passed,
                "factuality_gates_passed": comparison.factuality_gates_passed,
                "no_case_regressions": comparison.no_case_regressions,
                "accepted": comparison.accepted,
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
