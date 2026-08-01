import hashlib
import hmac
import json
from collections.abc import Mapping, Set

from src.schemas.inference import InferenceResponse, InferenceResultBundle


class BundleIntegrityError(ValueError):
    """Raised when bundle content does not match its declared digest."""


class BundleMismatchError(ValueError):
    """Raised when a bundle does not match the pending inference request."""


class DuplicateBundleError(ValueError):
    """Raised when the same valid bundle was already imported."""


def payload_digest(payload: InferenceResponse) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def create_bundle(payload: InferenceResponse) -> InferenceResultBundle:
    return InferenceResultBundle(
        payload=payload,
        payload_sha256=payload_digest(payload),
    )


def validate_bundle(
    raw_bundle: Mapping[str, object],
    *,
    expected_request_id: str,
    expected_model_revision: str,
    imported_hashes: Set[str] | None = None,
) -> InferenceResultBundle:
    bundle = InferenceResultBundle.model_validate(raw_bundle)
    actual_digest = payload_digest(bundle.payload)
    if not hmac.compare_digest(actual_digest, bundle.payload_sha256):
        raise BundleIntegrityError("bundle integrity check failed")
    if bundle.payload.request_id != expected_request_id:
        raise BundleMismatchError("bundle request does not match the pending request")
    if bundle.payload.model.model_revision != expected_model_revision:
        raise BundleMismatchError(
            "bundle model revision does not match the approved model"
        )
    if imported_hashes is not None and bundle.payload_sha256 in imported_hashes:
        raise DuplicateBundleError("bundle was already imported")
    return bundle
