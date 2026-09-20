from __future__ import annotations

from pathlib import Path

from skillopt.evaluation.scaling_library import (
    build_scaling_level,
    collect_distractors,
    write_scaling_suite,
)
from skillopt.rag_rule_selector import RuleMemory


BASE = """## Output Format
Return one concise answer.

## Search Rule A
Use source A.

## Search Rule B
Use source B.
"""

DISTRACTORS = """## Output Format
Return a final answer.

## Math Rule
Compute carefully.

## Law Rule
Apply the controlling authority.

## Sheet Rule
Check formulas and cell references.
"""


def test_scaling_level_preserves_base_ids_and_hits_exact_size(tmp_path: Path):
    base = tmp_path / "base.md"
    source = tmp_path / "other.md"
    base.write_text(BASE, encoding="utf-8")
    source.write_text(DISTRACTORS, encoding="utf-8")
    base_memory = RuleMemory(BASE)
    candidates = collect_distractors(tmp_path, ["other.md"])

    content, manifest = build_scaling_level(
        base_skill_path=base,
        base_skill_relative_path="base.md",
        target_dynamic_rules=4,
        distractors=candidates,
    )
    memory = RuleMemory(content)

    assert memory.n_dynamic == 4
    assert set(base_memory.dynamic_rule_ids).issubset(memory.dynamic_rule_ids)
    assert manifest["n_base_dynamic_rules"] == 2
    assert manifest["n_distractor_rules"] == 2
    assert [row["role"] for row in manifest["rules"]].count("base") == 2


def test_scaling_suite_is_nested_and_reproducible(tmp_path: Path):
    (tmp_path / "base.md").write_text(BASE, encoding="utf-8")
    (tmp_path / "other.md").write_text(DISTRACTORS, encoding="utf-8")
    out = tmp_path / "suite"

    first = write_scaling_suite(
        project_root=tmp_path,
        base_skill_relative_path="base.md",
        distractor_source_paths=["other.md"],
        targets=[2, 4, 5],
        output_dir=out,
    )
    second = write_scaling_suite(
        project_root=tmp_path,
        base_skill_relative_path="base.md",
        distractor_source_paths=["other.md"],
        targets=[2, 4, 5],
        output_dir=out,
    )

    assert first == second
    ids_by_size = []
    for target in (2, 4, 5):
        memory = RuleMemory((out / f"library_{target:04d}.md").read_text(encoding="utf-8"))
        assert memory.n_dynamic == target
        ids_by_size.append(set(memory.dynamic_rule_ids))
    assert ids_by_size[0] < ids_by_size[1] < ids_by_size[2]
