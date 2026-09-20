#!/usr/bin/env python3
"""Disk-backed integrity gate for the ACL 2027 Phase 2 v4 runner."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HEX64 = re.compile(r"[0-9a-f]{64}")


class IntegrityError(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise IntegrityError(f"non-canonical SHA-256: {label}")
    return value


def manifest_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in manifest.items() if key != "aggregate_fingerprint"}


def verify_integrity(config_path: Path, manifest_path: Path, *, root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    config = load(config_path)
    manifest = load(manifest_path)
    if manifest.get("schema_version") != 4 or manifest.get("artifact") != "acl2027_phase2_staged_live_runner_preflight_v4":
        raise IntegrityError("v4 manifest schema or identity drift")
    if set(manifest) != {"schema_version", "artifact", "status", "binding_model", "bindings", "aggregate_fingerprint", "calls", "authorization_opened"}:
        raise IntegrityError("v4 manifest field drift")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict) or not bindings:
        raise IntegrityError("v4 manifest bindings missing")
    seen_paths: set[str] = set()
    for name, binding in bindings.items():
        if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
            raise IntegrityError(f"manifest binding schema drift: {name}")
        relative = binding["path"]
        expected = canonical_sha256(binding["sha256"], name)
        if not isinstance(relative, str) or relative in seen_paths:
            raise IntegrityError(f"manifest binding path drift: {name}")
        seen_paths.add(relative)
        path = (root / relative).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise IntegrityError(f"manifest binding escapes root: {name}") from exc
        if not path.is_file() or sha256_file(path) != expected:
            raise IntegrityError(f"manifest disk hash drift: {name}")
    aggregate = canonical_sha256(manifest.get("aggregate_fingerprint"), "aggregate_fingerprint")
    if stable(manifest_payload(manifest)) != aggregate:
        raise IntegrityError("aggregate fingerprint drift")
    expected_root = canonical_sha256(config.get("integrity_root", {}).get("expected_aggregate_fingerprint"), "config integrity root")
    if aggregate != expected_root:
        raise IntegrityError("frozen integrity root mismatch")
    if manifest.get("calls") != {"network_calls": 0, "provider_calls": 0, "model_calls": 0, "qwen_calls": 0, "paid_api_calls": 0}:
        raise IntegrityError("zero-call manifest counters drift")
    if manifest.get("authorization_opened") is not False:
        raise IntegrityError("manifest authorization state drift")
    return config, manifest
