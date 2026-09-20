"""Deterministic construction of rule-library scaling suites.

The scaling treatment keeps the task's original rules unchanged and adds
cross-task distractor rules.  This varies routing difficulty without splitting
or duplicating the in-domain rules, avoiding a granularity confound.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from skillopt.rag_rule_selector import RuleMemory
from skillopt.rule_identity import rule_text_hash, stable_rule_id


@dataclass(frozen=True)
class DistractorRule:
    source_path: str
    source_rule_id: str
    source_heading: str
    source_index: int
    rendered_text: str
    rule_id: str
    text_hash: str


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _clean_heading(heading: str) -> str:
    heading = re.sub(r"^#{1,6}\s*", "", heading).strip()
    return " ".join(heading.split()) or "Untitled"


def render_distractor(rule) -> str:
    """Wrap a parsed rule as an explicit, independently parsed H2 section."""
    heading = _clean_heading(rule.heading)
    return f"## Distractor {rule.rule_id}: {heading}\n{rule.body.strip()}".strip()


def collect_distractors(
    project_root: str | Path,
    source_paths: Iterable[str],
    *,
    excluded_source_rule_ids: set[str] | None = None,
) -> list[DistractorRule]:
    """Collect unique dynamic rules from deterministic cross-task sources."""
    root = Path(project_root)
    excluded = excluded_source_rule_ids or set()
    seen_source_hashes: set[str] = set()
    seen_rendered_ids: set[str] = set()
    candidates: list[DistractorRule] = []
    for relative_path in source_paths:
        path = root / relative_path
        if not path.exists():
            raise FileNotFoundError(f"Distractor source does not exist: {relative_path}")
        memory = RuleMemory(path.read_text(encoding="utf-8"))
        for rule in memory.dynamic_rules:
            if rule.rule_id in excluded or rule.text_hash in seen_source_hashes:
                continue
            # A fallback "Full Skill" rule can contain nested H2/H3 sections and
            # would expand into several rules when appended to the base library.
            if re.search(r"(?m)^#{2,3}\s+", rule.body):
                continue
            rendered = render_distractor(rule)
            rendered_id = stable_rule_id(rendered)
            if rendered_id in seen_rendered_ids:
                continue
            seen_source_hashes.add(rule.text_hash)
            seen_rendered_ids.add(rendered_id)
            candidates.append(DistractorRule(
                source_path=str(relative_path).replace("\\", "/"),
                source_rule_id=rule.rule_id,
                source_heading=_clean_heading(rule.heading),
                source_index=rule.index,
                rendered_text=rendered,
                rule_id=rendered_id,
                text_hash=rule_text_hash(rendered),
            ))
    return candidates


def build_scaling_level(
    *,
    base_skill_path: str | Path,
    base_skill_relative_path: str,
    target_dynamic_rules: int,
    distractors: list[DistractorRule],
) -> tuple[str, dict]:
    """Build one exact-size library and its machine-readable catalog."""
    base_path = Path(base_skill_path)
    base_text = base_path.read_text(encoding="utf-8").strip()
    base_memory = RuleMemory(base_text)
    if target_dynamic_rules < base_memory.n_dynamic:
        raise ValueError(
            f"target_dynamic_rules={target_dynamic_rules} is smaller than base size "
            f"{base_memory.n_dynamic}"
        )
    needed = target_dynamic_rules - base_memory.n_dynamic
    if needed > len(distractors):
        raise ValueError(f"Need {needed} distractors but only {len(distractors)} are available")

    selected = distractors[:needed]
    chunks = [base_text, *(rule.rendered_text for rule in selected)]
    content = "\n\n".join(chunk for chunk in chunks if chunk).rstrip() + "\n"
    memory = RuleMemory(content)
    if memory.n_dynamic != target_dynamic_rules:
        raise RuntimeError(
            f"Generated library parsed as {memory.n_dynamic} dynamic rules; "
            f"expected {target_dynamic_rules}"
        )

    base_ids = set(base_memory.dynamic_rule_ids)
    selected_by_id = {rule.rule_id: rule for rule in selected}
    catalog = []
    for position, rule in enumerate(memory.dynamic_rules):
        item = {
            "position": position,
            "rule_id": rule.rule_id,
            "text_hash": rule.text_hash,
            "heading": _clean_heading(rule.heading),
            "role": "base" if rule.rule_id in base_ids else "distractor",
        }
        source = selected_by_id.get(rule.rule_id)
        if source is not None:
            item.update({
                "source_path": source.source_path,
                "source_rule_id": source.source_rule_id,
                "source_index": source.source_index,
            })
        else:
            item.update({
                "source_path": base_skill_relative_path.replace("\\", "/"),
                "source_rule_id": rule.rule_id,
                "source_index": rule.index,
            })
        catalog.append(item)

    manifest = {
        "schema_version": 1,
        "construction": "fixed in-domain base plus deterministic cross-task distractors",
        "target_dynamic_rules": target_dynamic_rules,
        "n_total_rules": memory.n_total,
        "n_core_rules": memory.n_core,
        "n_dynamic_rules": memory.n_dynamic,
        "n_base_dynamic_rules": base_memory.n_dynamic,
        "n_distractor_rules": needed,
        "base_skill_path": base_skill_relative_path.replace("\\", "/"),
        "base_skill_sha256": file_sha256(base_path),
        "rule_set_fingerprint": memory.rule_set_fingerprint,
        "dynamic_rule_ids": memory.dynamic_rule_ids,
        "rules": catalog,
    }
    return content, manifest


def write_scaling_suite(
    *,
    project_root: str | Path,
    base_skill_relative_path: str,
    distractor_source_paths: list[str],
    targets: list[int],
    output_dir: str | Path,
) -> dict:
    """Materialize all scaling levels and return the suite manifest."""
    root = Path(project_root)
    base_path = root / base_skill_relative_path
    base_memory = RuleMemory(base_path.read_text(encoding="utf-8"))
    distractors = collect_distractors(
        root, distractor_source_paths,
        excluded_source_rule_ids=set(base_memory.dynamic_rule_ids),
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    levels = []
    for target in sorted(set(targets)):
        content, manifest = build_scaling_level(
            base_skill_path=base_path,
            base_skill_relative_path=base_skill_relative_path,
            target_dynamic_rules=target,
            distractors=distractors,
        )
        stem = f"library_{target:04d}"
        markdown_path = out / f"{stem}.md"
        manifest_path = out / f"{stem}.json"
        markdown_path.write_text(content, encoding="utf-8")
        manifest["library_path"] = markdown_path.name
        manifest["library_sha256"] = file_sha256(markdown_path)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        levels.append({
            "target_dynamic_rules": target,
            "library_path": markdown_path.name,
            "manifest_path": manifest_path.name,
            "library_sha256": manifest["library_sha256"],
            "rule_set_fingerprint": manifest["rule_set_fingerprint"],
        })

    suite = {
        "schema_version": 1,
        "base_skill_path": base_skill_relative_path.replace("\\", "/"),
        "base_skill_sha256": file_sha256(base_path),
        "distractor_sources": [
            {"path": path.replace("\\", "/"), "sha256": file_sha256(root / path)}
            for path in distractor_source_paths
        ],
        "available_unique_distractors": len(distractors),
        "levels": levels,
    }
    (out / "suite_manifest.json").write_text(
        json.dumps(suite, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return suite
