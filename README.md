# Bibliographic Record AI Prompt Generator

## Usage:

1. download the code to a permanent location where it will live. (If it moves you will need to run install again)
2. Right click inside the folder created and open the Terminal, inside the terminal type: `python install.py`
3. Wait for the dependencies to install.
4. Once the shortcut is created, **drag it to Desktop or taskbar** as you wish.
5. Double click and the browser will automatically open

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
- 040: `<subfield code="a">XXX</subfield><subfield code="b">eng</subfield><subfield code="e">rda</subfield><subfield code="c">XXX</subfield>`
- 049: `<subfield code="a">XXX</subfield>`

**Leader:**
- Use `00000nam a22000007c 4500` (positions 06=a, 07=m, 17=c)

**ISBN & Format (Field 020):**
- ISBN: Not provided (extract from description if found)
- Book Format: Not provided
- **CRITICAL FORMATTING:** Place the ISBN in subfield $a. Place the format (e.g., hardcover, paperback) in subfield $q inside parentheses.
- Example: `<datafield tag="020" ind1=" " ind2=" "><subfield code="a">9781234567890</subfield><subfield code="q">(hardcover)</subfield></datafield>`

**008 fixed field (books):**
- Value: `260414s2026    ne            0|0 u eng d`
- Year: 2026
- Country code: ne 
- Index present (008/31): 0
- Biography (008/34): ' '
- Literary form (008/33): u (unknown)
- Language (008/35-37): eng same as cat language

**Field 020 (ISBN) Instructions:**
- Use ISBN: Check input metadata
- Use Book Format: Check input metadata
- IMPORTANT: Put the format in subfield $q enclosed in parentheses. 
  Example: `<datafield tag="020" ind1=" " ind2=" "><subfield code="a">1234567890</subfield><subfield code="q">(hardcover)</subfield></datafield>`

**Cataloging Language & Translation Instructions:**
- The language of cataloging is: **English** (eng).
- **Field 040 $b** MUST be set to `eng`.
- All descriptive text, notes, and physical descriptions (Field 300) MUST be in English.
- **Terminology Examples for Field 300:**
  - If English: Use "pages", "illustrations", "color", "cm".
  - If Dutch: Use "pagina's", "illustraties", "kleur", "cm".
- Use English for all general notes (500) and summary notes (520).

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
    <controlfield tag="008">260414s2026    ne            0|0 u eng d</controlfield>
    <datafield tag="020" ind1=" " ind2=" ">
        <subfield code="a">978...</subfield>
        <subfield code="q">(paperback)</subfield>
    </datafield>
    <datafield tag="040" ind1=" " ind2=" ">
        <subfield code="a">XXX</subfield>
        <subfield code="b">eng</subfield>
        <subfield code="e">rda</subfield>
        <subfield code="c">XXX</subfield>
    </datafield>
    <datafield tag="245" ind1="1" ind2="0">
        <subfield code="a">Title of the Book</subfield>
    </datafield>
</record>

**Input Metadata to Process:**
ISBN: 
Format: 

**General Metadata:** 
test

**Specific User Instructions:**
test

**Return only the MARCXML record in a code block to copy.**
```

