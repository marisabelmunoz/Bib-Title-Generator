"""
handlers/prompt.py
Builds AI cataloging prompts.

Two entry points:
  build_prompt        — generates a new MARC21 record from raw metadata.
  build_update_prompt — improves an existing MARC21 record retrieved from WorldCat.

When field_008_prebuilt is supplied (from the 008 Builder form) build_prompt
instructs the AI to copy it verbatim.  The legacy auto-construction path is
retained as a fallback when no pre-built value is provided.
"""

from datetime import datetime
from .config import load_institution_config

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

PLACE_LABELS = {
    "ne":  "Netherlands (ne)",
    "xxu": "United States (xxu)",
    "xxk": "United Kingdom (xxk)",
    "gw":  "Germany (gw)",
    "fr":  "France (fr)",
    "it":  "Italy (it)",
    "sp":  "Spain (sp)",
    "be":  "Belgium (be)",
    "au":  "Australia (au)",
    "cn":  "Canada (cn)",
}

BIOGRAPHY_LABELS = {
    " ": "No biographical information ( )",
    "a": "Autobiography (a)",
    "b": "Individual biography (b)",
    "c": "Collective biography (c)",
    "d": "Contains biographical information (d)",
    "e": "Biographical sketches (e)",
    "|": "No attempt to code (|)",
}

LANG_MAP = {
    "eng": "English",
    "dut": "Dutch (Nederlands)",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_prebuilt_008_section(field_008_prebuilt: str) -> str:
    """Return the prompt section used when the cataloger has pre-built the 008."""
    return f"""**008 fixed field — PREBUILT (do not modify):**

The 008 field has been constructed manually by the cataloger using the 008 Builder.
You MUST use it exactly as provided — character by character. Do NOT alter any position.

```
{field_008_prebuilt}
```

**DO NOT change any character in this 008 field.**
The field is guaranteed to be exactly 40 characters.
Your only task for the 008 is to copy it verbatim into:

```xml
<controlfield tag="008">{field_008_prebuilt}</controlfield>
```"""


def _build_auto_008_section(field_008, year_clean, place_clean, idx_clean, bio_clean, today_str) -> str:
    """Return the legacy prompt section that asks the AI to determine literary form, bio, and language."""
    return f"""**008 fixed field (books):**

**CRITICAL 008 CONSTRUCTION:**

The 008 field is pre-built as: `{field_008}`

You MUST replace `LANG_CODE_HERE` with the correct 3-character language code (e.g., 'dut', 'eng', 'fre').

DO NOT change anything else in the 008 field. Keep the `00`, the index value, and the biography code exactly as shown.

**The 008 field must be exactly 40 characters including spaces. Do not add or remove spaces.**

**CORRECT PATTERN (spaces exactly as shown):**
`260414s{year_clean}    {place_clean}           00{idx_clean}[LITFORM][BIO][LANGCODE] d`

**They must be consecutive characters including the spaces!**

Where:
- `[LITFORM]` = YOU determine (single character, position 33) - see literary form rules below
- `[BIO]` = YOU determine (single character, position 34) - see biography rules below
- `[LANGCODE]` = YOU determine (3 characters, positions 35-37) - see language rules below

**CRITICAL:** Do NOT copy 'u' or 'eng' from any example. You MUST analyze the input metadata and replace `[LITFORM]`, `[BIO]`, and `[LANGCODE]` with your determined values.

**STRICT POSITION MAPPING (40 characters exactly):**
**EXACT CHARACTER POSITIONS (count them, DO NOT RETURN RESULT UNTIL CORRECT!):**

| Position(s) | Content | Source |
|-------------|---------|--------|
| 00-05 | `{today_str}` | FIXED - Date entered |
| 06    | `s` | FIXED - Single known date |
| 07-10 | `{year_clean}` | From publication date |
| 11-14 | space space space space | FIXED |
| 15-17 | `{place_clean}` | From publisher country |
| 18-21 | space space space space | FIXED |
| 22    | space | FIXED |
| 23    | space | FIXED |
| 24-29 | space space space space space space | FIXED |
| 30    | `0` | FIXED |
| 31    | `{idx_clean}` | FIXED - Index value |
| 32    | space | FIXED |
| 33    | `[LITFORM]` | YOU ANALYZE |
| 34    | `[BIO]` | YOU ANALYZE |
| 35-37 | `[LANGCODE]` | YOU ANALYZE |
| 38    | space | FIXED |
| 39    | `d` | FIXED - Other cataloging source |

**Determining 008 Language Code (positions 35-37):**

Analyze the input metadata:
1. Any explicit "Taal"/"Language" field → use that code
2. The language of the title and subtitle
3. The language of the 520 summary/description
4. Author's name and publisher location as secondary clues

Never default to 'eng' without verification. When in doubt, use 'und'.

**Determining 008 Literary Form (position 33):**

ALL biographies, autobiographies, memoirs, and collective biographies are NON-FICTION.
Always use code '0' for position 33 when the work is biographical.

Codes:
- 0 = Non-fiction  1 = Fiction  f = Novels  j = Short stories
- p = Poetry  d = Dramas  e = Essays  h = Humor/satire
- i = Letters  m = Mixed forms  s = Speeches  u = Unknown (last resort)

- Value: `{field_008}`
- Year: {year_clean}
- Country code: {place_clean if place_clean.strip() in PLACE_LABELS else "Unknown (verify against LOC country codes)"}
- Index present (008/31): {idx_clean}
- Biography (008/34): {bio_clean!r}
- Literary form (008/33): analyze content to determine this
- Language (008/35-37): analyze content to determine this"""


# ---------------------------------------------------------------------------
# Public API — new record
# ---------------------------------------------------------------------------

def build_prompt(biography, index_val, year, place, description, isbn, format_book,
                 cat_lang, extra_instructions, field_008_prebuilt=None):
    """
    Build the full AI cataloging prompt for creating a new MARC21 record.

    Parameters
    ----------
    field_008_prebuilt : str | None
        When provided (from the 008 Builder form) the prompt instructs the AI to
        copy this value verbatim.  When None the legacy auto-determination path
        is used instead.
    """
    inst_config      = load_institution_config()
    institution_code = inst_config["institution_code"]

    # ── Fallback values (used in legacy path and for example block) ──────────
    year_clean  = year.strip() if (year.strip().isdigit() and len(year.strip()) == 4) \
                  else str(datetime.now().year)
    place_clean = place.strip().ljust(3)[:3]
    bio_clean   = biography if biography in BIOGRAPHY_LABELS else " "
    idx_clean   = "1" if index_val == "1" else "0"
    today_str   = datetime.now().strftime("%y%m%d")
    lang_name   = LANG_MAP.get(cat_lang, "English")

    # ── 008 section of prompt ────────────────────────────────────────────────
    if field_008_prebuilt and len(field_008_prebuilt) == 40:
        field_008_for_example = field_008_prebuilt
        section_008 = _build_prebuilt_008_section(field_008_prebuilt)
    else:
        field_008 = (
            f"{today_str}s{year_clean}    {place_clean}           "
            f"00{idx_clean}{bio_clean}LANG_CODE_HERE  d"
        )
        field_008_for_example = field_008
        section_008 = _build_auto_008_section(
            field_008, year_clean, place_clean, idx_clean, bio_clean, today_str
        )

    # ── Full prompt ──────────────────────────────────────────────────────────
    prompt = f"""You are a professional cataloger following RDA guidelines and MARC21 formatting.

Your task: analyze the input metadata provided and generate a complete MARC21 bibliographic record in MARCXML format.

**Request body format:** application/marcxml+xml

**Constraints**
- NEVER make up any information that is not provided
- NEVER create a control number
- DO NOT make assumptions or make up information for what is missing

**Always set these fixed fields:**
- 040: `<subfield code="a">{institution_code}</subfield><subfield code="b">{cat_lang}</subfield><subfield code="e">rda</subfield><subfield code="c">{institution_code}</subfield>`
- 049: `<subfield code="a">{institution_code}</subfield>`

**Leader:**
- Use `00000nam a22000007ci 4500` (positions 06=a, 07=m)
- 17=c if ISBD punctuation is NOT present in the title you generate, otherwise 17=i if you omit ISBD punctuation

**ISBN & Format (Field 020):**
- ISBN: {isbn if isbn else "Not provided (extract from description if found)"}
- Book Format: {format_book if format_book else "Not provided"}
- **CRITICAL FORMATTING:** Place the ISBN in subfield $a. Place the format (e.g., hardcover, paperback) in subfield $q inside parentheses.
- Example: `<datafield tag="020" ind1=" " ind2=" "><subfield code="a">9781234567890</subfield><subfield code="q">(hardcover)</subfield></datafield>`

{section_008}

**Field 020 (ISBN) Instructions:**
- Use ISBN: {isbn if isbn else "Check input metadata"}
- Use Book Format: {format_book if format_book else "Check input metadata"}
- IMPORTANT: Put the format in subfield $q enclosed in parentheses.
  Example: `<datafield tag="020" ind1=" " ind2=" "><subfield code="a">{isbn if isbn else '1234567890'}</subfield><subfield code="q">({format_book if format_book else 'hardcover'})</subfield></datafield>`

**Cataloging Language & Translation Instructions:**
- The language of cataloging is: **{lang_name}** ({cat_lang}).
- **Field 040 $b** MUST be set to `{cat_lang}`.
- All descriptive text, notes, and physical descriptions (Field 300) MUST be in {lang_name}.
- **Terminology Examples for Field 300:**
  - If English: Use "pages", "illustrations", "color", "cm".
  - If Dutch: Use "pagina's", "illustraties", "kleur", "cm".
- Use {lang_name} for all general notes (500) and summary notes (520).

**RDA core elements to include:**
- 072 #7 (nur value ONLY if given on the description!)
- 100/110/111 (creator)
- 245 (title statement)
- 250 (edition) - exactly as stated on the text, if not stated, do not include this field
- 264 #1 (production/publication) – use RDA $b publisher, $c date
- 264 #4 copyright year (always based on publication date unless stated on the text)
- 300 (physical description) – pagination, illustrations, dimensions; determine if illustrations are present based on description and include in physical description
- 336/337/338 (content, media, carrier type – RDA mandatory)
    When cataloging in Dutch (dut), always use the Dutch RDA terms for fields 336, 337, and 338, and append '/dut' to the source codes in subfield $2 (e.g., rdacontent/dut).
    - dutch: 336: rdacontent/dut · 337: rdamedium/dut · 338: rdacarrier/dut
    - english: 336: rdacontent · 337: rdamedium · 338: rdacarrier
- 490 / 830 (series)
- 500 (general notes as needed)
- 504 (bibliography note) if the description mentions bibliography or sources, register, notes, etc.
- 546 (language note) if the description mentions the language of the content in a way that is not clear from the 008 analysis
- 650/651 (subjects) — keep them as #4 for evaluation; you can also use FAST headings and LCSH
- 655 (genre/form) if the description mentions a specific genre or form
- 700/710 (other contributors) : if the role is mentioned, include it in the appropriate subfields ($4 and $e for role)
  Use https://www.loc.gov/marc/relators/relacode.html as reference for MARC21 relator codes.

**Example format (MARCXML):**

<record>
    <leader>00000nam a22000007i 4500</leader>
    <controlfield tag="008">{field_008_for_example}</controlfield>
    <datafield tag="020" ind1=" " ind2=" ">
        <subfield code="a">{isbn if isbn else "978..."}</subfield>
        <subfield code="q">({format_book if format_book else "paperback"})</subfield>
    </datafield>
    <datafield tag="040" ind1=" " ind2=" ">
        <subfield code="a">{institution_code}</subfield>
        <subfield code="b">{cat_lang}</subfield>
        <subfield code="e">rda</subfield>
        <subfield code="c">{institution_code}</subfield>
    </datafield>
    <datafield tag="245" ind1="1" ind2="0">
        <subfield code="a">Title of the Book</subfield>
    </datafield>
</record>

**Input Metadata to Process:**
ISBN: {isbn if isbn else "no isbn"}
Format: {format_book if isbn else "no isbn tag to include this, ignore"}

**General Metadata:**
{description}

**Specific User Instructions:**
{extra_instructions if extra_instructions else "None provided."}


**Return only the MARCXML record in a code block to copy.**
"""
    return prompt.strip()


# ---------------------------------------------------------------------------
# Public API — improve / update existing record
# ---------------------------------------------------------------------------

def build_update_prompt(
    existing_marcxml: str,
    extra_instructions: str,
    cat_lang: str,
    additional_metadata: str = "",
) -> str:
    """
    Build an AI prompt for improving an existing MARC21 record retrieved from WorldCat.

    The prompt instructs the AI to:
      1. Start from the supplied MARCXML record verbatim.
      2. Apply the cataloger's improvement instructions.
      3. Return the complete, corrected record — never a partial diff.


    Parameters
    ----------
    existing_marcxml : str
        The raw MARCXML currently stored in WorldCat.
    extra_instructions : str
        Free-text instructions from the cataloger describing what to improve,
        add, correct, or remove.
    cat_lang : str
        Cataloging language code ('eng' or 'dut').
    additional_metadata : str
        Any supplementary metadata the cataloger wants the AI to use
        (e.g., publisher blurb, table of contents, back-cover text).
    """
    inst_config      = load_institution_config()
    institution_code = inst_config["institution_code"]
    lang_name        = LANG_MAP.get(cat_lang, "English")

    extra_block = (
        f"\n**Additional metadata / context supplied by cataloger:**\n{additional_metadata}\n"
        if additional_metadata.strip()
        else ""
    )

    instructions_block = (
        extra_instructions.strip()
        if extra_instructions.strip()
        else "No specific instructions provided — review the record for completeness and correct any obvious errors."
    )

    prompt = f"""You are a professional cataloger following RDA guidelines and MARC21 formatting.

Your task: **improve the existing MARC21 bibliographic record** provided below.

---

## Ground rules

- **Start from the existing record** — do not discard data that is already correct.
- **NEVER invent information** that is not present in the existing record or the additional metadata below.
- **NEVER remove the control number** (field 001) or any other fixed fields unless explicitly instructed.
- **Preserve the OCN** (001 / 035 fields) exactly as found.
- The cataloging language is **{lang_name}** ({cat_lang}).
  - Field 040 $b MUST be `{cat_lang}`.
  - All new descriptive text (300, 500, 520 …) MUST be in {lang_name}.
- IMPORTANT SO AS NOT TO BREAK THE RECORD: **Leave field 040 exactly as found** — do not add, delete, or change any subfield or institution code under any circumstance. The only allowed action is to add $e rda if it is missing; otherwise, copy the field verbatim.
- Return the **complete** improved record — not a diff, not a summary, not a partial extract.
- When suggesting subject headings, stick to a maximum of 5 and always add them under `ind2=4` without $2 unless explicitly instructed.


---

## Improvement instructions from the cataloger

{instructions_block}

---

**Cataloging Language & Translation Instructions:**
- The language of cataloging is: **{lang_name}** ({cat_lang}).
- **Field 040 $b** MUST be set to `{cat_lang}`.
- All descriptive text, notes, and physical descriptions (Field 300) MUST be in {lang_name}.
- **Terminology Examples for Field 300:**
  - If English: Use "pages", "illustrations", "color", "cm".
  - If Dutch: Use "pagina's", "illustraties", "kleur", "cm".
- Use {lang_name} for all general notes (500) and summary notes (520).


## RDA fields to verify / complete (if not already present and applicable)
- 072 #7 (nur value ONLY if given on the description!)
- 020  ISBN — subfield $a for number, $q for format in parentheses
- 040  Language of cataloging ($b {cat_lang}), description conventions ($e rda)
- 049  Holdings symbol ({institution_code})
- 100/110/111  Creator with correct RDA relationship designator
- 245  Title statement — check indicators and punctuation
- 250  Edition (only if stated in the resource)
- 264 _1  Publication statement — RDA form
- 264 _4  Copyright date
- 300  Physical description in {lang_name} (pages/pagina's, illustrations/illustraties, cm)
- 336/337/338  RDA content/media/carrier — use {'rdacontent/dut · rdamedium/dut · rdacarrier/dut' if cat_lang == 'dut' else 'rdacontent · rdamedium · rdacarrier'}
- 490/830  Series
- 500  General notes
- 504  Bibliography note (if sources/register are mentioned)
- 520  Summary note in {lang_name}
- 546  Language note (if content language is ambiguous)
- 650/651  Subject headings (#4 for local evaluation; FAST/LCSH welcome)
- 655  Genre/form (if applicable)
- 700/710  Added entries for contributors with relator codes
  (reference: https://www.loc.gov/marc/relators/relacode.html)
{extra_block}
---

**Specific User Instructions:**
{extra_instructions if extra_instructions else "None provided."}



## Existing MARCXML record to improve

```xml
{existing_marcxml.strip()}
```

---

**Return only the complete improved MARCXML record in a single code block, ready to submit to the OCLC API.**
"""
    return prompt.strip()
