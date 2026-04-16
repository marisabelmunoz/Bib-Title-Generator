"""
handlers/prompt.py
Builds the AI cataloging prompt with valid 40-character 008 field and detailed instructions.
You can always adjust this as needed for your case.
"""

from datetime import datetime
from .config import load_institution_config

# Mapping of place codes to country names for display
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

    # auto generate from: https://www.loc.gov/standards/codelists/countries.xml
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
    "dut": "Dutch (Nederlands)"
}

def build_prompt(biography, index_val, year, place, description, isbn, format_book, cat_lang, extra_instructions):
    """
    Build the full AI cataloging prompt with a guaranteed 40-character 008 field,
    including specific instructions for ISBN and Format.
    """
    # Load institution configuration
    inst_config = load_institution_config()
    institution_code = inst_config["institution_code"]
    
    # 1. Clean and validate inputs
    year_clean = year.strip() if (year.strip().isdigit() and len(year.strip()) == 4) else str(datetime.now().year)
    place_clean = place.strip().ljust(3, ' ')[:3] # Ensure exactly 3 chars
    bio_clean = biography if biography in BIOGRAPHY_LABELS else " "
    idx_clean = "1" if index_val == "1" else "0"

    # 2. Construct exactly 40 chars for 008
    # need to have correct date of today
    today_str = datetime.now().strftime("%y%m%d") # YYMMDD format for date entered
    lang_name = LANG_MAP.get(cat_lang, "English")
    field_008 = f"{today_str}s{year_clean}    {place_clean}           00{idx_clean}{bio_clean}LANG_CODE_HERE  d"
    
    prompt = f"""You are a professional cataloger following RDA guidelines and MARC21 formatting.

Your task: analyze the input metadata provided and generate a complete MARC21 bibliographic record in MARCXML format.

**Request body format:** application/marcxml+xml

**Constrains**
- NEVER make up any information that is not provided
- NEVER create a control number
- DO NOT make assumptions or make up information for what is missing

**Always set these fixed fields:**
- 040: `<subfield code="a">{institution_code}</subfield><subfield code="b">{cat_lang}</subfield><subfield code="e">rda</subfield><subfield code="c">{institution_code}</subfield>`
- 049: `<subfield code="a">{institution_code}</subfield>`

**Leader:**
- Use `00000nam a22000007c 4500` (positions 06=a, 07=m, 17=c)

**ISBN & Format (Field 020):**
- ISBN: {isbn if isbn else "Not provided (extract from description if found)"}
- Book Format: {format_book if format_book else "Not provided"}
- **CRITICAL FORMATTING:** Place the ISBN in subfield $a. Place the format (e.g., hardcover, paperback) in subfield $q inside parentheses.
- Example: `<datafield tag="020" ind1=" " ind2=" "><subfield code="a">9781234567890</subfield><subfield code="q">(hardcover)</subfield></datafield>`

**008 fixed field (books):**

**CRITICAL 008 CONSTRUCTION:**

The 008 field is pre-built as: `{field_008}`

You MUST replace `LANG_CODE_HERE` with the correct 3-character language code (e.g., 'dut', 'eng', 'fre').

DO NOT change anything else in the 008 field. Keep the `00`, the index value, and the biography code exactly as shown.

**The 008 field must be exactly 40 characters including spaces. Do not add or remove spaces.**

**CORRECT PATTERN (spaces exactly as shown):**
`260414s{year}    {place}           00{index_val}[LITFORM][BIO][LANGCODE] d`

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
| 11-12 | space space | FIXED | ALWAYS INCLUDE THESE 2 SPACES BEFORE PLACE CODE!
| 13-14 | space space | FIXED | ALWAYS INCLUDE THESE 2 SPACES BEFORE PLACE CODE!
| 15-17 | `{place_clean}` | From publisher country |
| 18-21 | space space space space | FIXED | ALWAYS INCLUDE THESE 4 SPACES BEFORE THE INDEX VALUE!
| 22    | space | FIXED |
| 23    | `r` | FIXED - Reproduction (not a reproduction, but this is the correct code for books) |
| 24-29 | space space space space space space | FIXED |
| 30    | `0` | FIXED - No nature of contents |
| 31    | `{index_val}` | FIXED - Separator |
| 32    | space | FIXED | ALWAYS INCLUDE THIS SPACE BEFORE LITFORM!!! 
| 33    | `[LITFORM]` | YOU ANALYZE |
| 34    | `[BIO]` | YOU ANALYZE |
| 35-37 | `[LANGCODE]` | YOU ANALYZE |
| 38    | space | FIXED |
| 39    | `d` | FIXED - Other cataloging source | ALWAYS INCLUDE THIS AT THE END! DO NOT CHANGE IT!

**Length verification:** Count each position including spaces above. Total = 40 characters, not less, nor more!
YYMMDDsYYYY____xx_____r______###_#_lan__d

CRITICAL: Verify before proceding:
1. The date is in YYMMDD format and is exactly 6 characters.
2. The publication year is exactly 4 characters.
3. The place code is exactly 3 characters.
4. The index value is either '0' or '1'.
5. The literary form and biography codes are single characters.
6. The language code is exactly 3 characters.
7. The cataloguing source code 'd' is at the end.
8. The total length is exactly 40 characters.

**Determining 008 Language Code (positions 35-37):**

CRITICAL: This is the language of the WORK CONTENT, NOT the cataloging language.

Analyze the input metadata in this order:
1. Any explicit "Taal"/"Language" field → use that code
2. The language of the title and subtitle
3. The language of the 520 summary/description
4. The author's name and publisher location as secondary clues

Rules:
- Never default to 'eng'
- Never copy the 040 $b cataloging language without verification
- When in doubt after analysis, use 'und' (undetermined)

Examples from real cases:
- Title "De goeroe en de baron" + Dutch summary → code 'dut'
- Title "The Great Gatsby" + English summary → code 'eng'  
- Title "Le Petit Prince" + French summary → code 'fre'

**Determining 008 Literary Form (position 33):**

CRITICAL: This identifies the literary genre of the WORK CONTENT. Position 34 (Biography) is a SEPARATE field that works alongside position 33, not instead of it.

Analyze the input metadata in this order:
1. Any explicit genre/literary form terms (e.g., "roman", "novel", "poëzie", "essays", "toneelstuk")
2. The content and narrative style described in the 520 summary
3. Subject headings or classification codes (e.g., NUR, BISAC)
4. Author's known works or author role

**Core rule: ALL biographies, autobiographies, memoirs, and collective biographies are NON-FICTION.** Always use code '0' for position 33 when the work is biographical. The biography type (individual, collective, autobiography) is recorded in position 34 ONLY — it NEVER changes position 33 to 'u' or any other code.

Rules:
- Never default to 'u' (unknown) without attempting analysis
- If the work is a biography → position 33 = '0' (non-fiction) AND position 34 = appropriate biography code
- If the work is non-fiction but not a biography → position 33 = '0' and position 34 = ' ' (blank)
- Use '1' or specific codes ('f', 'j', 'p', etc.) only for imaginative/creative works
- When truly ambiguous after full analysis, use 'u'

**Codes reference (position 33):**
- 0 = Non-fiction (biographies, history, textbooks, journalism, self-help, science)
- 1 = Fiction (general fiction)
- f = Novels
- j = Short stories
- p = Poetry
- d = Dramas
- e = Essays
- h = Humor, satire
- i = Letters
- m = Mixed forms
- s = Speeches
- u = Unknown (only as last resort)

**Position 34 (Biography) quick reference (used WITH position 33='0'):**
- a = Autobiography
- b = Individual biography (one person, written by someone else)
- c = Collective biography (multiple persons)
- d = Contains biographical information
- ' ' (blank) = Not a biography

Examples from real cases:
- Title "De goeroe en de baron" + journalist author + biography of Krishnamurti and Van Pallandt → position 33 = '0', position 34 = 'c'
- Title "Nelson Mandela: A Biography" + individual life story → position 33 = '0', position 34 = 'b'
- Title "Mijn leven" (My Life) + autobiography → position 33 = '0', position 34 = 'a'
- Title "De aanslag" + fictional narrative → position 33 = 'f' or '1', position 34 = ' '
- Title "Verzameld werk" + poetry collection → position 33 = 'p', position 34 = ' '

**Common mistake to avoid:** DO NOT set position 33 to 'u' just because you set position 34 to 'a', 'b', or 'c'. A biography is non-fiction first, biography second.

- Value: `{field_008}`
- Year: {year_clean}
# if:  "not match on list, verify https://www.loc.gov/standards/codelists/countries.xml"
- Country code: {place_clean if place_clean.strip() in PLACE_LABELS else "Unknown (verify against LOC country codes : https://www.loc.gov/marc/countries/countries_code.html)"}
- Index present (008/31): {idx_clean}
- Biography (008/34): {bio_clean!r}
- Literary form (008/33): analyze content to determine this
- Language (008/35-37) : analyze content to determine this 

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

**RDA core elements to include :**
- 072 #7 (nur value ONLY if given on the description!)
- 100/110/111 (creator)
- 245 (title statement)
- 250 (edition)
- 264 #1(production/publication) – use RDA $b publisher, $c date
- 264 #4 copyright year (always based on publication date unless stated on the text)
- 300 (physical description) – pagination, illustrations, dimensions (all in English)
- 336/337/338 (content, media, carrier type – RDA mandatory)
- 490 / 830 (series)
- 500 (general notes as needed)
- 650/651 (subjects)
- 700/710 (other contributors)

**Example format (MARCXML):**

<record>
    <leader>00000nam a22000007c 4500</leader>
    <controlfield tag="008">{field_008}</controlfield>
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

**Before outputting, verify the 008 field is exactly 40 characters and follows the position mapping above. Analyze the input metadata carefully to determine the correct codes for literary form, biography, and language!**

**Return only the MARCXML record in a code block to copy.**
"""
    return prompt.strip()