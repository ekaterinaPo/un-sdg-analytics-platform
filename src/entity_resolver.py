"""
Resolve region/country references in a natural-language question against the
actual values in the SDG database, BEFORE the question ever reaches the LLM
agent. Two ambiguity classes exist in this dataset:

1. Region words people would naturally use ("Asian countries", "Middle East")
   don't map 1:1 onto the 7 exact SDR region strings the data actually uses
   (e.g. "Asian" overlaps both 'East & South Asia' and 'E. Europe & C. Asia',
   since the latter literally contains "Asia" - it's "Central Asia").
2. Country names can be ambiguous (e.g. "Korea" -> 'Korea, Rep.' vs
   'Korea, Dem. Rep.') or spelled per the World Bank/SDR convention rather
   than colloquially (e.g. 'Egypt, Arab Rep.').

Resolving these locally, in plain Python, against the database's own current
values is instant and free - no reason to make the LLM discover this by
trial-and-error SQL, which is exactly what drove up cost and turn count in
earlier agent runs (see logs/agent_queries.jsonl). Always reads the live
database rather than a cached snapshot, so this can never go stale when the
database is rebuilt - there is no separate file to remember to update.

This is a best-effort heuristic, not a robust NLP pipeline: it will have
both false positives (flagging a word that wasn't meant as a region/country)
and false negatives (missing a real reference). Treat it as a cheap filter
that catches the common, expensive cases - not a guarantee.
"""

import re
import sqlite3
import difflib

DB_PATH_DEFAULT = __import__("os").path.join(
    __import__("os").path.dirname(__file__), "..", "data", "processed", "sdg_analytics.db"
)

# Acronym/shorthand regions need aliases - their canonical string doesn't
# contain the natural-language words a person would type. Multi-word
# descriptive regions (e.g. "Sub-Saharan Africa", "East & South Asia") need
# no alias - they're matched automatically from their own words, see
# _region_words().
REGION_ALIASES = {
    "MENA": ["middle east", "north africa"],
    "LAC": ["latin america", "caribbean"],
}

_SENTENCE_STARTERS = {
    "The", "This", "That", "What", "Which", "Who", "How", "Since", "Are",
    "Is", "Do", "Does", "Compare", "Show", "List", "Find",
}


def load_entities(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Read the current set of regions and countries directly from the database."""
    conn = sqlite3.connect(db_path)
    try:
        regions = [
            r[0] for r in
            conn.execute("SELECT DISTINCT region FROM countries WHERE region IS NOT NULL")
        ]
        countries = [
            {"code": code, "name": name}
            for code, name in conn.execute("SELECT country_code, country_name FROM countries")
        ]
    finally:
        conn.close()
    return {"regions": regions, "countries": countries}


def _region_words(region: str) -> set:
    # drop short tokens like "E.", "C.", "&" - keep words that carry meaning
    return {w.lower() for w in re.findall(r"[A-Za-z]{4,}", region)}


def _matching_regions(question: str, regions: list) -> list:
    q = question.lower()

    exact = [r for r in regions if r.lower() in q]
    if exact:
        return exact

    alias_hits = [
        r for r, aliases in REGION_ALIASES.items()
        if r in regions and any(a in q for a in aliases)
    ]
    if alias_hits:
        return alias_hits

    # substring match, not exact-word match: catches "Asian" containing "asia"
    return [r for r in regions if any(w in q for w in _region_words(r))]


def _candidate_country_phrases(question: str) -> list:
    """
    Naive proper-noun detection: runs of capitalized words. Lowercases just
    the sentence-initial word first - English capitalizes the first word of
    any sentence regardless of whether it's a proper noun, and left as-is
    that would glue onto a following real proper noun (e.g. "Compare Korea"
    read as one phrase instead of finding "Korea" alone).
    """
    words = question.split()
    if words:
        words[0] = words[0].lower()
    normalized = " ".join(words)
    phrases = re.findall(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b", normalized)
    return [p for p in phrases if p not in _SENTENCE_STARTERS]


def _matching_countries(phrase: str, countries: list):
    """Returns (candidates, is_exact). is_exact True means no prompt needed."""
    exact = [
        c for c in countries
        if c["name"].lower() == phrase.lower() or c["code"].lower() == phrase.lower()
    ]
    if exact:
        return exact, True

    phrase_lower = phrase.lower()
    # This dataset names many countries "<name>, <qualifier>" (Korea, Rep. /
    # Korea, Dem. Rep. / Egypt, Arab Rep. / Congo, Dem. Rep. ...). A plain
    # colloquial name is a prefix of the part before the comma - catch that
    # directly, since difflib's ratio penalizes the length difference too
    # heavily to catch it reliably (e.g. "Korea" vs "Korea, Rep." scores
    # well below a cutoff that avoids false positives elsewhere).
    prefix_hits = [
        c for c in countries
        if c["name"].lower().split(",")[0].strip() == phrase_lower
    ]
    if prefix_hits:
        return prefix_hits, len(prefix_hits) == 1

    names = [c["name"] for c in countries]
    close = difflib.get_close_matches(phrase, names, n=4, cutoff=0.72)
    return [c for c in countries if c["name"] in close], False


def _ask_choice(prompt: str, options: list):
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print("  0. none of these - leave the question as written")
    while True:
        choice = input("Choose a number: ").strip()
        if choice in ("0", ""):
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("Please enter a valid number.")


def resolve_entities(question: str, entities: dict) -> str:
    """
    Check the question against known regions/countries. Ask interactively
    only when there's a real ambiguity or a near-miss spelling; an exact,
    unambiguous match is passed through untouched. Returns the (possibly
    rewritten) question.
    """
    regions = entities["regions"]
    countries = entities["countries"]

    # Resolve countries first: if the question already names a specific
    # country exactly, skip region-ambiguity checks entirely - a country
    # name is a stronger, sufficient signal, and region words often appear
    # inside country names themselves (e.g. "South" in "South Africa"),
    # which would otherwise falsely trigger a region prompt.
    country_phrases = _candidate_country_phrases(question)
    has_exact_country = False

    for phrase in country_phrases:
        matches, is_exact = _matching_countries(phrase, countries)
        if is_exact:
            has_exact_country = True
            continue
        if not matches:
            continue
        names = [c["name"] for c in matches]
        chosen = _ask_choice(
            f"'{phrase}' doesn't exactly match a country name in this database. Did you mean:",
            names,
        )
        if chosen:
            question = question.replace(phrase, chosen)
            has_exact_country = True

    if not has_exact_country:
        region_hits = _matching_regions(question, regions)
        if len(region_hits) > 1:
            chosen = _ask_choice(
                f"This question's region is ambiguous in this database - "
                f"which one do you mean?",
                region_hits,
            )
            if chosen:
                question = f"{question} (region = '{chosen}')"

    return question
