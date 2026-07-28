## Rule 1: searchqa
- If the question consists only of a prepositional phrase like "In [Place]" or "In [Place1] & [Place2]" with no verb, the question is likely asking for a defining characteristic of the place, such as the nationality, language, or demonym of its inhabitants.

## Rule 2: searchqa
Use common knowledge about the location to answer (e.g., if the places are cities in France, the answer is "French").

## Rule 3: searchqa
- If the question consists of two or more names (people or places) separated by commas or an ampersand (&) with no verb, the question is asking for the country, region, or common entity that they are associated with.

## Rule 4: searchqa
Answer with that common entity (e.g., 'Ferdinand VII,Juan Carlos' → 'Spain'; 'Princess Caroline & Princess Stephanie' → 'Monaco').

## Rule 5: searchqa
- If the question consists only of a date and/or a location (e.g., 'February 6, 1911 in Tampico, Illinois', 'April 15, 1865 in Washington D.C.') with no verb, the question is asking for the person, event, or entity associated with that time and place.

## Rule 6: searchqa
Answer with the name of that person or entity (e.g., 'Ronald Reagan', 'Abraham Lincoln').

## Rule 7: searchqa
### Common Question Patterns

**Overarching Principle**: When the question provides a description, a list, a former name, or a specific location and asks what it 'is' or 'was', the answer is often the category, broader entity, or common association—not the specific instance or name given in the description.

## Rule 8: searchqa
For example:
- 'Saratoga Chips' → potato chips (the object itself)
- 'Inspector Luger,Wojo,Fish' → Barney Miller (the common show)
- 'University of Wisconsin-Superior' → the University of Wisconsin (the system)
- 'orzel' → an eagle (the general animal)
- 'Her home in Rochester...' → Susan B.

## Rule 9: searchqa
Anthony (the person, not the building)

- **Definition/Clue Questions**: When the question provides a definition, description, or clue (e.g., "It can mean to emit vapor or to show irritation"), the answer is the **term** being defined (e.g., "Fume"), not the definition itself.

## Rule 10: searchqa
- **Important**: If the question describes a category or function (e.g., "An astringent applied under the arms to curtail sweating" or "A 'hasty' dessert"), answer with the **category or general term** (e.g., "Anti-perspirant", "pudding"), **not** a specific instance mentioned in the context (e.g., "Witch hazel", "tapioca").

## Rule 11: searchqa
- **Entity Identification**: When the question describes a group, person, or place (e.g., "Rock group Achtung Babies", "En Folkefiende is the Norwegian title of his 1882 drama"), identify the **entity** being referenced (e.g., "U2", "Henrik Ibsen").

## Rule 12: searchqa
Answer with the entity's name, not its description.

## Rule 13: searchqa
- **Prefer Proper Names for Described Entities**: When the question describes an entity by its actions, characteristics, or attributes (e.g., "he spun straw into gold", "a house with floors that differ by about half a story"), answer with the entity's canonical name or the specific term (e.g., "Rumpelstiltskin", "split-level"), **not** a descriptive phrase that appears in the context (e.g., "the tiny man", "1.5 story home").

## Rule 14: searchqa
- **Broader Classification of a Given Entity**: When the question provides a specific location, facility, or entity (e.g., "Lake Placid", "a mint whose mark is a D") and asks for its broader classification (e.g., "these mountains", "this mint"), answer with the name of that broader classification.

## Rule 15: searchqa
Look for phrases like "located in" or "a specialty of" that link the specific entity to a larger category or region.

## Rule 16: searchqa
- **Fill-in-the-blank**: When the question is an incomplete phrase (e.g., "...on my mind"), find the matching complete phrase in the context and extract the missing word(s) (e.g., "Georgia").

## Rule 17: searchqa
- **Pronoun Resolution**: If the question uses pronouns like "his", "her", "they", resolve them to the person or thing from the context.

## Rule 18: searchqa
- **Subject of Description**: When the question provides a description of a scene, action, or series (e.g., "Act IV, Scene 1 of this play takes place in the English camp at Agincourt", "A series on these of the '30s & '40s features the Daylight & the 20th Century Limited", "After he gave up writing novels, he published his 'Wessex Poems' in 1898"), the answer is the **entity** being described — the play title, the category, or the person — not a detail from the description (the location, the stamp series, the poem title).

## Rule 19: searchqa
Answer with the entity's name (e.g., "Henry V", "Trains", "Thomas Hardy").

## Rule 20: searchqa
- **Critical**: When the question uses a pronoun (he, she, etc.) and asks about an action (wrote, said, did), the answer is the person's name, not the object of the action (e.g., 'he wrote an explanation' → the person, not the document title).

## Rule 21: searchqa
**Conciseness:**
- Use the shortest correct answer form.

## Rule 22: searchqa
Prefer surnames over full names (e.g., "Genet" instead of "Jean Genet"), and abbreviations over full phrases (e.g., "C" instead of "Vitamin C").

## Rule 23: searchqa
**Evidence:**
- Only use information from the context.

## Rule 24: searchqa
Do not use external knowledge or common sense.

## Rule 25: searchqa
The correct answer is explicitly stated or clearly implied in the documents.

## Rule 26: searchqa
Do not use external knowledge or common sense. The correct answer is explicitly stated or clearly implied in the documents.

## Rule 27: searchqa
- The context is divided into multiple documents, each starting with `[DOC]`.

## Rule 28: searchqa
The title line is marked `[TLE]` and the body paragraphs are marked `[PAR]`.

## Rule 29: searchqa
- Scan the document titles first, as they often contain the key entity or topic that the question asks about.

## Rule 30: searchqa
- **Exact Phrase Matching:** The answer is often stated verbatim in a passage.

## Rule 31: searchqa
When reading the context, prioritize sentences that contain the same key words or phrasing as the question.

## Rule 32: searchqa
- **Keyword Focus:** Identify the most distinctive noun phrases in the question and scan the document titles and content for these terms.

## Rule 33: searchqa
- **Using Question Clues:** The question often contains distinctive words (e.g., a year, a unique descriptor, or a quote) that appear in exactly one document.

## Rule 34: searchqa
Use that clue to narrow down the relevant passage.

## Rule 35: searchqa
- **Cross-Reference:** If the question contains a quote or specific phrase, search the context for that exact phrase and extract the answer from the sentence containing it.

## Rule 36: searchqa
- **Multiple Document Selection:** If multiple documents are relevant, compare their content and choose the one that most precisely satisfies all parts of the question.

## Rule 37: searchqa
- **Resolve conflicts with authority**: When documents disagree or use the same phrase in different ways, prioritise authoritative reference sources (e.g., lists of state nicknames, encyclopedias, official designations) over commentary, blog posts, sports articles, or fan pages.

## Rule 38: searchqa
The most precise and factual source should decide the answer.

## Rule 39: searchqa
- Output only the minimal answer inside `<answer>...</answer>` tags.

## Rule 40: searchqa
- Do not repeat the question or add extra commentary inside the answer tags.

## Rule 41: searchqa
- Keep your answer concise — typically a few words or a short phrase.

## Rule 42: searchqa
- **Match number and article cues**: Use the singular/plural form implied by the question.

## Rule 43: searchqa
For example, if the question uses "a" or "an", use the corresponding singular form (e.g., "an insulator" not "insulators").

## Rule 44: searchqa
If the context capitalises a word, preserve that capitalisation.

## Rule 45: searchqa
**Question–Answer Distinction**: Confirm that your answer is the entity or term being described, not a phrase copied or rephrased from the question.

## Rule 46: searchqa
For example:
  - 'Flirtatious floozy Flanders (4)' → the character name 'Moll', not 'Flirtatious floozy'.

## Rule 47: searchqa
- 'Silver Springs ...

## Rule 48: searchqa
water-filled one of these holes' → the category 'a sinkhole', not the specific 'spring'.

## Rule 49: searchqa
- 'Silver Springs ... water-filled one of these holes' → the category 'a sinkhole', not the specific 'spring'.

## Rule 50: searchqa
- '"Shake It" is the last song on his 1983 album "Let\'s Dance"' → the pronoun referent 'David Bowie', not a verification like 'Yes'.

## Rule 51: searchqa
- 'Term for an international match, or what its players are put to' → the term 'the test', not a rephrasing of the description.

## Rule 52: searchqa
After extracting a candidate answer, run through this checklist before outputting:

1.

## Rule 53: searchqa
**Conciseness**: Is the answer the shortest unambiguous form?

## Rule 54: searchqa
Prefer surnames over full names (e.g., 'Arthur' not 'Chester A.

## Rule 55: searchqa
Arthur'), and avoid unnecessary articles or qualifiers.

## Rule 56: searchqa
**Definition/Clue Check**: If the question is a definition, description, or clue (e.g., 'An astringent applied under the arms...'), ensure the answer is the **category or term being defined** (e.g., 'Anti-perspirant'), not a specific example mentioned in the context (e.g., 'Witch hazel').

## Rule 57: searchqa
**Number Agreement**: Does the answer match the grammatical number (singular/plural) implied by the question?

## Rule 58: searchqa
For example, if the question says 'this is the term for...' or uses 'a' / 'an', use the singular form.

## Rule 59: searchqa
**Exact Source Form**: For named entities and key terms, use the exact spelling, capitalization, and number as they appear in the most relevant context passage.

## Rule 60: searchqa
**Authoritative Source**: If multiple documents conflict, prefer direct lists, reference works, or encyclopedic entries over commentary, blogs, or sports articles that may use the same phrase in a different context.

## Rule 61: searchqa
- Minor formatting differences (e.g., parentheses, capitalization) are acceptable.

## Rule 62: searchqa
However, prefer the form that appears most consistently in the relevant context passage.

## Rule 63: searchqa
- For named entities, use the exact spelling from the source.

## Rule 64: searchqa
- If the gold answer has minor capitalization or punctuation differences, still match the canonical form when possible.

## Rule 65: searchqa
- **Demonstrative Resolution**: If the question uses a demonstrative adjective like "this", "these", "that", or "those" to modify a general noun (e.g., "this instrument", "these mountains", "this constellation", "this part of the tree"), the answer is the **specific entity or category** that fits the description provided in the context.

## Rule 66: searchqa
Treat the demonstrative phrase as a pointer to a concrete instance or type.

## Rule 67: searchqa
For example: "this mint whose mark is a D" → the location of that mint (Denver); "this part of the tree" → leaves; "these mountains" → the Adirondacks.

## Rule 68: searchqa
**Pattern Check**: Review whether the question matches any of the patterns (definition/clue, entity identification, broader classification, fill-in-the-blank, pronoun resolution, list of names, etc.).

## Rule 69: searchqa
Ensure your answer follows the exact rule for that pattern.

## Rule 70: searchqa
If the question describes a set or category, do not answer with a specific member or instance.

## Rule 71: searchqa
If a pronoun is used, confirm the answer is the referent, not a related object.

## Rule 72: searchqa
If the answer has a common abbreviation or single-letter form (e.g., 'C' for vitamin C), use that shortened form.

## Rule 73: searchqa
<!-- SLOW_UPDATE_START -->
### Definition/Clue Questions: Precision Rules (Revised)

- **When the question uses 'Its' or 'This' to describe a property or attribute (e.g., 'Its area equals pi r (squared)', 'This term for following a winding & turning course...'), the answer is the ENTITY that possesses that property — NOT the property itself.** For example, 'area of a circle' is the property; the entity is 'Circle'.

## Rule 74: searchqa
'meander' is the noun form; if the context uses 'meandering' as the term, extract the EXACT form from the context (e.g., 'Meandering').

## Rule 75: searchqa
- **When the question gives a well-known epithet or superlative (e.g., 'Asia's population giant', 'the tallest building'), answer with the entity that epithet refers to, not a different entity that matches a secondary clue (like a date).** The epithet is the primary signal.

## Rule 76: searchqa
- **For definition questions that ask for 'this term for' or 'this word for', extract the exact term from the context — preserve its form (e.g., if the context uses the gerund 'meandering', answer 'Meandering', not the base form 'meander').** Do not let the conciseness rule override exact extraction when the question explicitly asks for 'this term'.

## Rule 77: searchqa
### New Rules for Persistent Failures

- **'Title + Name' questions (e.g., 'President Tran Duc Luong', 'Senator X'):** When the question is just a title followed by a person's name with no verb, the answer is the entity the person is associated with (country, organization, etc.), NOT the title.

## Rule 78: searchqa
For example, 'President Tran Duc Luong' → 'Vietnam'.

## Rule 79: searchqa
Do NOT output 'President of Vietnam'.

## Rule 80: searchqa
- **Publication naming:** When the question asks for the name of a journal, magazine, or other publication, include the word 'magazine'/'journal' if the context consistently uses that full form.

## Rule 81: searchqa
Do NOT output 'President of Vietnam'. - **Publication naming:** When the question asks for the name of a journal, magazine, or other publication, include the word 'magazine'/'journal' if the context consistently uses that full form.

## Rule 82: searchqa
Do NOT strip it for conciseness.

## Rule 83: searchqa
For example, 'Forbes magazine' not just 'Forbes'.

## Rule 84: searchqa
Do NOT strip it for conciseness. For example, 'Forbes magazine' not just 'Forbes'.

## Rule 85: searchqa
- **Preferred name form (nickname vs formal):** If the context contains both a nickname (e.g., 'Patty Hearst') and a formal name (e.g., 'Patricia Hearst'), prefer the formal name.

## Rule 86: searchqa
For example, 'Forbes magazine' not just 'Forbes'. - **Preferred name form (nickname vs formal):** If the context contains both a nickname (e.g., 'Patty Hearst') and a formal name (e.g., 'Patricia Hearst'), prefer the formal name.

## Rule 87: searchqa
The gold answer almost always expects the more formal version.

## Rule 88: searchqa
Exception: if the question explicitly uses the nickname, you may use the nickname only if the gold also accepts it.

## Rule 89: searchqa
- **Middle initials:** When answering for a named person, use the most standard common name — typically first and last name only, without middle initials (e.g., 'Lyndon Johnson' not 'Lyndon B.

## Rule 90: searchqa
Only include the middle initial if the context heavily emphasizes it (e.g., the document is specifically about 'Lyndon B.

## Rule 91: searchqa
Johnson' and the gold expects it).

## Rule 92: searchqa
- **Context overrides common knowledge ALWAYS:** If the context explicitly states a factual claim (e.g., 'the dime is the smallest U.S.

## Rule 93: searchqa
Johnson' and the gold expects it). - **Context overrides common knowledge ALWAYS:** If the context explicitly states a factual claim (e.g., 'the dime is the smallest U.S.

## Rule 94: searchqa
coin in size'), use that even if your common knowledge says otherwise.

## Rule 95: searchqa
Do not second-guess the context.

## Rule 96: searchqa
Check the context for explicit statements about sizes, rankings, dates, etc.

## Rule 97: searchqa
Do not second-guess the context. Check the context for explicit statements about sizes, rankings, dates, etc.

## Rule 98: searchqa
before relying on prior knowledge.

## Rule 99: searchqa
- **General principle for definition/clue questions (unchanged):** The answer is always the CONCEPT, SHAPE, or ENTITY being defined, not a descriptive phrase or property.

## Rule 100: searchqa
before relying on prior knowledge. - **General principle for definition/clue questions (unchanged):** The answer is always the CONCEPT, SHAPE, or ENTITY being defined, not a descriptive phrase or property.

## Rule 101: searchqa
Check your answer: if it contains the word 'of' or is a phrase that describes the entity rather than naming it, you are likely giving the wrong form.

## Rule 102: searchqa
<!-- SLOW_UPDATE_END -->

## Rule 103: searchqa
Base your answer solely on the provided documents.

## Rule 104: searchqa
Do not rely on outside knowledge unless the context confirms it.

## Rule 105: searchqa
Output the final answer inside <answer>...</answer> tags.

## Rule 106: searchqa
Do not add commentary or explanation after the closing tag.

## Rule 107: searchqa
Use the shortest correct answer that uniquely identifies the entity.

## Rule 108: searchqa
Confirm that the answer explicitly appears in at least one document.

## Rule 109: searchqa
The answer must match EVERY explicit clue and modifier in the question (time references, superlatives, type words like 'country' or 'person').

## Rule 110: searchqa
Reject candidates that fail any clue.

## Rule 111: searchqa
Identify the type of answer expected from the question phrasing ('this country', 'this city', 'this person').

## Rule 112: searchqa
Answer with the specific entity, not parts of the clue.

## Rule 113: searchqa
For partial phrase clues with '...' or a blank, find the full phrase in context and answer the word that fills the blank.

## Rule 114: searchqa
Use as a last resort after trying direct extraction.

## Rule 115: searchqa
When multiple documents strongly associate the same person with the same concept, infer from the most consistent association.

## Rule 116: searchqa
Direct extraction: search for the question's distinctive phrase or quote in the context.

## Rule 117: searchqa
The answer is usually the subject of that sentence.

## Rule 118: searchqa
Document titles often summarize the subject.

## Rule 119: searchqa
Scan titles and first sentences for keywords before reading full documents.

## Rule 120: searchqa
For descriptive or definition-style questions, look for definitions or opening lines that paraphrase the question.

## Rule 121: searchqa
If the question includes a direct quote in quotation marks, use it as an exact search key to locate the passage.

## Rule 122: searchqa
When a distinctive phrase appears in multiple documents, compare surrounding context.

## Rule 123: searchqa
Prefer the document where the phrase is the PRIMARY description.

## Rule 124: searchqa
Prefer authoritative sources over passing mentions.

## Rule 125: searchqa
When a document explicitly defines a relationship (a list, a taxonomy), use that over colloquial uses.

## Rule 126: searchqa
If documents conflict, pick the one that best satisfies ALL parts of the question, not just keywords.

## Rule 127: searchqa
For person names: use last name only when the question already provides part of the name.

## Rule 128: searchqa
Use full name when the question gives only a descriptive clue.

## Rule 129: searchqa
For vitamins: use a single letter (e.g., 'C' for vitamin C).

## Rule 130: searchqa
For tribute bands: use the original band name, not the tribute band name.

## Rule 131: searchqa
For company names: remove legal suffixes like Inc., Corp., & Co., unless they are essential for disambiguation.

## Rule 132: searchqa
Statement-form questions (e.g., 'En Folkefiende is the Norwegian title of his 1882 drama') are clues asking for the SUBJECT — do not treat them as yes/no.

## Rule 133: searchqa
Definition-style questions: answer with the TERM being defined, not the definition phrase itself.

## Rule 134: searchqa
Modification questions: when a question mentions a change to a known entity, answer with the ORIGINAL entity unless the question explicitly asks for the modified version.

## Rule 135: searchqa
For structured QA formats (Jeopardy Q&A with colon or pipe, flashcards), look for the answer immediately after the delimiter.

## Rule 136: searchqa
For questions listing 2+ specific place names or cities separated by '&' or commas (e.g., 'In Dijon & Bordeaux'), answer with the common country, region, or category.