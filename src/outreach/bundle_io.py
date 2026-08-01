import json
from collections.abc import Set
from pathlib import Path

from src.outreach.bundles import validate_bundle
from src.schemas.inference import InferenceResultBundle

MAX_BUNDLE_BYTES = 1_000_000


class BundleReadError(ValueError):
    """Raised when a result-bundle file cannot be safely decoded."""


def load_and_validate_bundle(
    path: Path,
    *,
    expected_request_id: str,
    expected_model_revision: str,
    imported_hashes: Set[str] | None = None,
) -> InferenceResultBundle:
    try:
        if path.stat().st_size > MAX_BUNDLE_BYTES:
            raise BundleReadError("bundle exceeds the 1 MB size limit")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except BundleReadError:
        raise
    except json.JSONDecodeError as exc:
        raise BundleReadError("bundle is not valid JSON") from exc
    except OSError as exc:
        raise BundleReadError(f"unable to read bundle: {exc}") from exc
    if not isinstance(raw, dict):
        raise BundleReadError("bundle JSON must be an object")
    return validate_bundle(
        raw,
        expected_request_id=expected_request_id,
        expected_model_revision=expected_model_revision,
        imported_hashes=imported_hashes,
    )
