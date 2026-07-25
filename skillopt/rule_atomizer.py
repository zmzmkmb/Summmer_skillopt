"""Atomic rule definitions for SearchQA skill.

Manually atomized from the best Core Only skill (0.7336 test).
Each rule is a single, named judgment or operation — not a multi-thousand-char section.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class AtomicRule:
    id: str           # stable rule ID
    text: str         # the rule content (1-3 sentences)
    is_core: bool     # always active
    tags: list[str]   # semantic tags for future classification


# ── Core rules (always active) ──────────────────────────────────────────
CORE_RULES: list[AtomicRule] = [
    AtomicRule("R01", "Base your answer solely on the provided documents. Do not rely on outside knowledge unless the context confirms it.", True, ["safety", "grounding"]),
    AtomicRule("R02", "Output the final answer inside <answer>...</answer> tags. Do not add commentary or explanation after the closing tag.", True, ["output_format", "safety"]),
    AtomicRule("R03", "Use the shortest correct answer that uniquely identifies the entity. For partial phrase clues, answer the noun that completes the phrase.", True, ["output_format", "concision"]),
    AtomicRule("R04", "Confirm that the answer explicitly appears in at least one document (or is strongly implied). Cross-check: multiple supporting documents increase confidence.", True, ["safety", "verification"]),
    AtomicRule("R05", "The answer must match EVERY explicit clue and modifier in the question (time references, superlatives, type words like 'country' or 'person'). If multiple candidates exist, reject any that fail any clue.", True, ["reasoning", "all_clue_matching"]),
    AtomicRule("R06", "Identify the type of answer expected from the question phrasing ('this country', 'this city', 'this person'). Answer with the specific entity that the clue describes, not parts of the clue itself.", True, ["reasoning", "answer_type"]),
]

# ── Dynamic rules (retrievable per query) ───────────────────────────────
DYNAMIC_RULES: list[AtomicRule] = [
    # ── Extraction & phrase matching ──
    AtomicRule("R07", "Direct extraction: search for the question's distinctive phrase or quote in the context. The answer is usually the subject of that sentence.", False, ["extraction", "phrase_matching"]),
    AtomicRule("R08", "Document titles often summarize the subject. Scan titles and first sentences for keywords from the question before reading full documents.", False, ["extraction", "document_scanning"]),
    AtomicRule("R09", "For descriptive or definition-style questions, look for definitions or opening lines that paraphrase the question.", False, ["extraction", "definition"]),
    AtomicRule("R10", "If the question includes a direct quote in quotation marks, use it as an exact search key to locate the passage.", False, ["extraction", "quote_matching"]),

    # ── Disambiguation & conflict ──
    AtomicRule("R11", "When a distinctive phrase appears in multiple documents, compare surrounding context. Prefer the document where the phrase is the PRIMARY description of its subject.", False, ["disambiguation", "phrase_conflict"]),
    AtomicRule("R12", "Prefer authoritative sources over passing mentions. When a document explicitly defines a relationship (a list, a taxonomy), use that over colloquial uses.", False, ["disambiguation", "authority"]),
    AtomicRule("R13", "If documents conflict, pick the one that best satisfies ALL parts of the question, not just keywords.", False, ["disambiguation", "conflict_resolution"]),

    # ── Entity normalization ──
    AtomicRule("R14", "For person names: use last name only when the question already provides part of the name (e.g., 'named Chester'→'Arthur'). Use full name when the question gives only a descriptive clue without any name part.", False, ["entity", "person_name"]),
    AtomicRule("R15", "For vitamins: use a single letter (e.g., 'C' for vitamin C).", False, ["entity", "vitamin"]),
    AtomicRule("R16", "For tribute bands: use the original band name, not the tribute band name (e.g., 'U2' for a U2 tribute band).", False, ["entity", "band_name"]),
    AtomicRule("R17", "For company names: remove legal suffixes like Inc., Corp., & Co., unless they are essential for disambiguation.", False, ["entity", "company_name"]),

    # ── Question type handling ──
    AtomicRule("R18", "Statement-form questions (e.g., 'En Folkefiende is the Norwegian title of his 1882 drama') are clues asking for the SUBJECT — do not treat them as yes/no.", False, ["question_type", "statement"]),
    AtomicRule("R19", "Definition-style questions: answer with the TERM being defined, not the definition phrase itself. The answer is the headword.", False, ["question_type", "definition"]),
    AtomicRule("R20", "Modification questions: when a question mentions a change to a known entity, answer with the ORIGINAL entity unless the question explicitly asks for the modified version.", False, ["question_type", "modification"]),

    # ── Special patterns ──
    AtomicRule("R21", "For structured QA formats (Jeopardy Q&A with colon or pipe, flashcards), look for the answer immediately after the delimiter.", False, ["pattern", "structured_format"]),
    AtomicRule("R22", "For location lists (e.g., 'In Dijon & Bordeaux'), the answer is the common category they belong to (country, region, nationality).", False, ["pattern", "location_list"]),
    AtomicRule("R23", "For partial phrase clues ('... on my mind', 'hasty _____'), find the full phrase in context and answer the noun that completes it.", False, ["pattern", "phrase_completion"]),

    # ── Inference ──
    AtomicRule("R24", "Inference fallback: if no explicit answer is found, use strong contextual associations (a well-known link between person and concept). Prefer answers supported by multiple documents.", False, ["inference"]),
]

# ── Combined registry ────────────────────────────────────────────────────
ALL_RULES: list[AtomicRule] = CORE_RULES + DYNAMIC_RULES

# Rule texts for embedding
CORE_TEXTS: list[str] = [r.text for r in CORE_RULES]
DYNAMIC_TEXTS: list[str] = [r.text for r in DYNAMIC_RULES]

# Core text as concatenated string (for initial training)
CORE_TEXT_BLOCK: str = "\n\n".join(CORE_TEXTS)
