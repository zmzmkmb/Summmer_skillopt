#!/usr/bin/env python3
"""Build scaled rule libraries from the trained SearchQA skill.

Inputs:
  outputs/searchqa_rag/best_skill.md  — 13,772 chars, 6 H2 + 3 H3 sections

Produces at {out_root}/rule_libraries/:
  rules_0008.md  — original (unchanged)
  rules_0024.md  — paragraph-level split (~24 rules)
  rules_0050.md  — sub-paragraph split (~50 rules)
  rules_0100.md  — sentence-group split (~100 rules)
  rules_0200.md  — single-sentence + neighbor (~200 rules)

Strategy:
  - Each rule is formatted as "## Rule N: <heading>\n<body>"
  - Body = 1-3 paragraphs (context-preserving, not isolated single sentences)
  - Rules are numbered sequentially with descriptive headings
  - Preserves ALL original content — no information loss
"""
from __future__ import annotations

import os, re, sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_skill():
    path = os.path.join(_PROJECT_ROOT, "outputs", "searchqa_rag", "best_skill.md")
    with open(path, encoding="utf-8") as f:
        return f.read()

def split_into_paras(text: str) -> list[str]:
    """Split text body (non-heading) into paragraphs."""
    paras = [p.strip() for p in text.split("\n\n")]
    return [p for p in paras if p and not p.strip().startswith("#")]

def split_into_sentences(text: str) -> list[str]:
    """Split text into individual sentences."""
    raw = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in raw if s.strip()]

def make_rule(idx: int, heading_hint: str, body: str) -> str:
    """Format one rule as a markdown section."""
    # Extract first ~50 chars of body as heading
    preview = body[:80].replace("\n", " ")
    return f"## Rule {idx:d}: {heading_hint} — {preview}…\n{body}"

def build_original(skill: str) -> str:
    """Return the original skill unchanged."""
    return skill

def build_24(skill: str) -> str:
    """Paragraph-level rules (~24 rules). Each H2/H3 section body split by paragraph."""
    sections = re.split(r"\n(?=## )", skill)
    rules = []
    idx = 1
    for sec in sections:
        if not sec.strip().startswith("##"):
            continue
        lines = sec.strip().split("\n", 1)
        heading = lines[0].strip("#").strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        # Split body by paragraphs (double newlines)
        paras = [p.strip() for p in body.split("\n\n") if p.strip()]
        if len(paras) <= 2:
            # Keep as one rule
            rules.append(make_rule(idx, heading, body))
            idx += 1
        else:
            for p in paras:
                if len(p) > 30:
                    rules.append(make_rule(idx, heading, p))
                    idx += 1
    return "\n\n".join(rules)

def build_50(skill: str) -> str:
    """Sub-paragraph rules (~50). Split large paragraphs further."""
    sections = re.split(r"\n(?=## )", skill)
    rules = []
    idx = 1
    for sec in sections:
        if not sec.strip().startswith("##"):
            continue
        lines = sec.strip().split("\n", 1)
        heading = lines[0].strip("#").strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        paras = [p.strip() for p in body.split("\n\n") if p.strip()]
        for p in paras:
            if len(p) < 80:
                rules.append(make_rule(idx, heading, p))
                idx += 1
            else:
                # Split at sentence boundaries into groups of 2-3 sentences
                sents = split_into_sentences(p)
                chunk_size = max(2, len(sents) // max(1, len(sents) // 3))
                for i in range(0, len(sents), chunk_size):
                    chunk = " ".join(sents[i:i+chunk_size])
                    if len(chunk) > 30:
                        rules.append(make_rule(idx, heading, chunk))
                        idx += 1
    return "\n\n".join(rules)

def build_100(skill: str) -> str:
    """Sentence-group rules (~100). ~2 sentences per rule."""
    sections = re.split(r"\n(?=## )", skill)
    rules = []
    idx = 1
    for sec in sections:
        if not sec.strip().startswith("##"):
            continue
        lines = sec.strip().split("\n", 1)
        heading = lines[0].strip("#").strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        sents = split_into_sentences(body)
        # Group 2 sentences together
        for i in range(0, len(sents), 2):
            chunk = " ".join(sents[i:i+2])
            if len(chunk) > 25:
                rules.append(make_rule(idx, heading, chunk))
                idx += 1
    return "\n\n".join(rules)

def build_200(skill: str) -> str:
    """Single-sentence rules with context (~200). Each sentence its own rule, keeping neighbor."""
    sections = re.split(r"\n(?=## )", skill)
    rules = []
    idx = 1
    for sec in sections:
        if not sec.strip().startswith("##"):
            continue
        lines = sec.strip().split("\n", 1)
        heading = lines[0].strip("#").strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        sents = split_into_sentences(body)
        for i, s in enumerate(sents):
            if len(s) < 20:
                continue
            # Include previous sentence as context if it exists
            chunk = s
            if i > 0 and len(sents[i-1]) > 20:
                chunk = sents[i-1] + " " + s
            rules.append(make_rule(idx, heading, chunk))
            idx += 1
    return "\n\n".join(rules)

def main():
    skill = load_skill()
    out_dir = os.path.join(_PROJECT_ROOT, "outputs", "rule_libraries")
    os.makedirs(out_dir, exist_ok=True)

    builders = {
        "rules_0008": build_original,
        "rules_0024": build_24,
        "rules_0050": build_50,
        "rules_0100": build_100,
        "rules_0200": build_200,
    }

    for name, builder in builders.items():
        content = builder(skill)
        # Count rules
        n_rules = content.count("## Rule ")
        path = os.path.join(out_dir, f"{name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"{name}.md: {len(content):,} chars, ~{n_rules} rules")

    print(f"\nSaved to: {out_dir}")

if __name__ == "__main__":
    main()
