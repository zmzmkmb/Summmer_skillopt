"""Atomic rule definitions for SearchQA skill.

Each rule has:
- trigger: short phrase for TF-IDF retrieval (only this is indexed)
- text:    full instruction given to the target model when rule is retrieved

Current: 8 Core (always active) + 16 Dynamic (TF-IDF Top-5 retrieved).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AtomicRule:
    id: str
    text: str         # full instruction for execution (sent to model)
    trigger: str      # short trigger for TF-IDF retrieval (only this is indexed)
    is_core: bool
    tags: list[str]


# ── Core rules (always active) ──────────────────────────────────────────
CORE_RULES: list[AtomicRule] = [
    AtomicRule("R01",
        text="Base your answer solely on the provided documents. Do not rely on outside knowledge unless the context confirms it.",
        trigger="answer from context documents",
        is_core=True, tags=["safety", "grounding"]),
    AtomicRule("R02",
        text="Output the final answer inside <answer>...</answer> tags. Do not add commentary or explanation after the closing tag.",
        trigger="output answer format tags",
        is_core=True, tags=["output_format", "safety"]),
    AtomicRule("R03",
        text="Use the shortest correct answer that uniquely identifies the entity.",
        trigger="shortest correct answer entity",
        is_core=True, tags=["output_format", "concision"]),
    AtomicRule("R04",
        text="Confirm that the answer explicitly appears in at least one document.",
        trigger="verify answer appears in document",
        is_core=True, tags=["safety", "verification"]),
    AtomicRule("R05",
        text="The answer must match EVERY explicit clue and modifier in the question (time references, superlatives, type words like 'country' or 'person'). Reject candidates that fail any clue.",
        trigger="match all clues question",
        is_core=True, tags=["reasoning", "all_clue_matching"]),
    AtomicRule("R06",
        text="Identify the type of answer expected from the question phrasing ('this country', 'this city', 'this person'). Answer with the specific entity, not parts of the clue.",
        trigger="this country city person answer type",
        is_core=True, tags=["reasoning", "answer_type"]),
    AtomicRule("R23",
        text="For partial phrase clues with '...' or a blank, find the full phrase in context and answer the word that fills the blank.",
        trigger="ellipsis ... dots blank fill underscore complete phrase",
        is_core=True, tags=["pattern", "phrase_completion"]),
    AtomicRule("R24",
        text="Use as a last resort after trying direct extraction. When multiple documents strongly associate the same person with the same concept, infer from the most consistent association.",
        trigger="infer association consistent last resort fallback",
        is_core=True, tags=["inference"]),
]

# ── Dynamic rules (TF-IDF Top-5 retrieved per query) ────────────────────
DYNAMIC_RULES: list[AtomicRule] = [
    # ── Extraction & phrase matching ──
    AtomicRule("R07",
        text="Direct extraction: search for the question's distinctive phrase or quote in the context. The answer is usually the subject of that sentence.",
        trigger="distinctive phrase quote search context subject sentence",
        is_core=False, tags=["extraction", "phrase_matching"]),
    AtomicRule("R08",
        text="Document titles often summarize the subject. Scan titles and first sentences for keywords before reading full documents.",
        trigger="document title scan keywords first sentence",
        is_core=False, tags=["extraction", "document_scanning"]),
    AtomicRule("R09",
        text="For descriptive or definition-style questions, look for definitions or opening lines that paraphrase the question.",
        trigger="descriptive definition question opening lines paraphrase",
        is_core=False, tags=["extraction", "definition"]),
    AtomicRule("R10",
        text="If the question includes a direct quote in quotation marks, use it as an exact search key to locate the passage.",
        trigger="quotation marks direct quote exact search",
        is_core=False, tags=["extraction", "quote_matching"]),

    # ── Disambiguation & conflict ──
    AtomicRule("R11",
        text="When a distinctive phrase appears in multiple documents, compare surrounding context. Prefer the document where the phrase is the PRIMARY description.",
        trigger="phrase appears multiple documents compare context primary description",
        is_core=False, tags=["disambiguation", "phrase_conflict"]),
    AtomicRule("R12",
        text="Prefer authoritative sources over passing mentions. When a document explicitly defines a relationship (a list, a taxonomy), use that over colloquial uses.",
        trigger="authoritative source explicit definition list taxonomy",
        is_core=False, tags=["disambiguation", "authority"]),
    AtomicRule("R13",
        text="If documents conflict, pick the one that best satisfies ALL parts of the question, not just keywords.",
        trigger="documents conflict pick best satisfies question",
        is_core=False, tags=["disambiguation", "conflict_resolution"]),

    # ── Entity normalization ──
    AtomicRule("R14",
        text="For person names: use last name only when the question already provides part of the name. Use full name when the question gives only a descriptive clue.",
        trigger="person name last first full surname descriptive clue author writer actor",
        is_core=False, tags=["entity", "person_name"]),
    AtomicRule("R15",
        text="For vitamins: use a single letter (e.g., 'C' for vitamin C).",
        trigger="vitamin single letter",
        is_core=False, tags=["entity", "vitamin"]),
    AtomicRule("R16",
        text="For tribute bands: use the original band name, not the tribute band name.",
        trigger="tribute band original name",
        is_core=False, tags=["entity", "band_name"]),
    AtomicRule("R17",
        text="For company names: remove legal suffixes like Inc., Corp., & Co., unless they are essential for disambiguation.",
        trigger="company corporation business Inc Corp Ltd legal suffix brand name",
        is_core=False, tags=["entity", "company_name"]),

    # ── Question type handling ──
    AtomicRule("R18",
        text="Statement-form questions (e.g., 'En Folkefiende is the Norwegian title of his 1882 drama') are clues asking for the SUBJECT — do not treat them as yes/no.",
        trigger="statement form clue asking for subject title of his",
        is_core=False, tags=["question_type", "statement"]),
    AtomicRule("R19",
        text="Definition-style questions: answer with the TERM being defined, not the definition phrase itself.",
        trigger="definition term being defined headword word means term refers to",
        is_core=False, tags=["question_type", "definition"]),
    AtomicRule("R20",
        text="Modification questions: when a question mentions a change to a known entity, answer with the ORIGINAL entity unless the question explicitly asks for the modified version.",
        trigger="changed renamed modified altered original title name from to",
        is_core=False, tags=["question_type", "modification"]),

    # ── Special patterns ──
    AtomicRule("R21",
        text="For structured QA formats (Jeopardy Q&A with colon or pipe, flashcards), look for the answer immediately after the delimiter.",
        trigger="Jeopardy game show trivia Q&A answer question",
        is_core=False, tags=["pattern", "structured_format"]),
    AtomicRule("R22",
        text="For questions listing 2+ specific place names or cities separated by '&' or commas (e.g., 'In Dijon & Bordeaux'), answer with the common country, region, or category.",
        trigger="cities places Dijon Bordeaux & and country region category",
        is_core=False, tags=["pattern", "location_list"]),
]

# ── Derived convenience lists ───────────────────────────────────────────
CORE_TEXTS: list[str] = [r.text for r in CORE_RULES]
DYNAMIC_TEXTS: list[str] = [r.trigger for r in DYNAMIC_RULES]
CORE_TEXT_BLOCK: str = "\n\n".join(CORE_TEXTS)
