# Bibliographic Record AI Prompt Generator


## Usage:

1. download and extract the code to a permanent location where it will live. (If it moves you will need to run install again)
2. Right click inside the folder created and open the Terminal, inside the terminal type: `python install.py`
3. Wait for the dependencies to install.
4. Once the shortcut is created, **drag it to Desktop or taskbar** as you wish.
5. Double click and the browser will automatically open
6. For setting up the API, please read the **about** page.

See the About page for more information.

## Idea:

I have experience both with programming and guest satisfaction for the hotel industry. My role during the hotel days was to take feedback and improve the experience of both guests and colleagues. So I am always in search of optimization and excuses to play with code. 

As part of the adoption of AI in order to create more accurate bibliographic records, I realized we were all constantly asking AI models to generate the record based on a book at hand. We would then proceed to copy and paste line by line on our cataloguing system. The request from my colleague was "I wish I could just then send it to the catalogue". Which ignited the idea, "You can!"

## How does it work:

The script runs on a python flask server locally. 

#### install.py
- This script will create the shortcut which you can add to your desktop. 
#### app.py
- This is the main script, it will run the server and automatically open the browser for you.

#### application flow:
- User sets up the **configuration** before starting. The configuration is used for the API. You do not need to write your real name or contact, but this is used to identify the API used. So if there are issues, OCLC can find the requests and troubleshoot.
- On the **Bibliographic Record screen**, user selects what kind of record to create.
- On the **textbox** bellow the setup, user will add any information at hand
- On the **Extra Instructions** box, user can add more specific requests.
- User press `copy`
- On the chosen AI, user pastes the code.
- On the **API box**, user paste the result and send to Worldcat API.
- User is responsible for verifying accuracy and correcting mistakes.

#### prompt generated:

```
You are a professional cataloger following RDA guidelines and MARC21 formatting.

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

The 008 field MUST be exactly 40 characters. Use the following structure with placeholders you must fill:

Base pattern: `260414s{year}    {place}           0|{index_val} [LITFORM][BIO][LANGCODE] d`

Where:
- `[LITFORM]` = YOU determine (single character, position 33) - see literary form rules below
- `[BIO]` = YOU determine (single character, position 34) - see biography rules below  
- `[LANGCODE]` = YOU determine (3 characters, positions 35-37) - see language rules below

**CRITICAL:** Do NOT copy 'u' or 'eng' from any example. You MUST analyze the input metadata and replace `[LITFORM]`, `[BIO]`, and `[LANGCODE]` with your determined values.

Example of correct output after your analysis:
- For a Dutch collective biography: `260414s2026    ne           0|1 0c dut d`
- For an English novel: `260414s2026    xxu           0|1 f   eng d`
- For a Dutch poetry collection: `260414s2026    ne           0|1 p   dut d`

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
- If the work is non-fiction but not a biography → position 33 = '0' and position 34 = ' ' (blank) or '0' (no biographical material)
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
- Title "De goeroe en de baron" + journalist author + biography of Krishnamurti and Van Pallandt → position 33 = '0', position 34 = 'c' (collective biography)
- Title "Nelson Mandela: A Biography" + individual life story → position 33 = '0', position 34 = 'b'
- Title "Mijn leven" (My Life) + autobiography → position 33 = '0', position 34 = 'a'
- Title "De aanslag" + fictional narrative → position 33 = 'f' or '1', position 34 = ' ' (blank)
- Title "Verzameld werk" + poetry collection → position 33 = 'p', position 34 = ' '

**Common mistake to avoid:** DO NOT set position 33 to 'u' just because you set position 34 to 'a', 'b', or 'c'. A biography is non-fiction first, biography second.

- Year: {year_clean}
- Country code: {place_clean if place_clean.strip() in PLACE_LABELS else "Unknown (verify against LOC country codes)"}
- Index present (008/31): {idx_clean}

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

**RDA core elements to include when available:**
- 072 #7 (nur value ONLY if given on the description!)
- 100/110/111 (creator)
- 245 (title statement)
- 250 (edition)
- 264 (production/publication) – use RDA $b publisher, $c date
- 264 copyright year (based on publication date unless stated on the text)
- 300 (physical description) – pagination, illustrations, dimensions (all in English)
- 336/337/338 (content, media, carrier type – RDA mandatory)
- 490 / 830 (series)
- 500 (general notes as needed)
- 650/651 (subjects)
- 700/710 (other contributors)

**Example format (MARCXML):**

<record>
    <leader>00000nam a22000007c 4500</leader>
    <controlfield tag="008">260414s{year}    {place}           0|{index_val} [LITFORM][BIO][LANGCODE] d</controlfield>
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
```

## Todo
- [rda relators](https://help-nl.oclc.org/Metadata_Services/GGC/Richtlijnen/RDA_-_Resource_Description_and_Access/Relatiecodes_-_Algemene_inleiding/5.Engelse_en_Nederlandse_betekenis_van_relatiecodes_en_toelichting) - add to instructions to use this for person