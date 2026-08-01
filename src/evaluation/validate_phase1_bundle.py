import argparse
from pathlib import Path

from src.outreach.bundle_io import load_and_validate_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a reviewed Phase 1 Colab inference-result bundle."
    )
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--model-revision", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    bundle = load_and_validate_bundle(
        args.bundle,
        expected_request_id=args.request_id,
        expected_model_revision=args.model_revision,
    )
    payload = bundle.payload
    print(
        "Validated bundle",
        bundle.payload_sha256,
        "for",
        payload.model.model_id,
        payload.model.model_revision,
    )


if __name__ == "__main__":
    main()
