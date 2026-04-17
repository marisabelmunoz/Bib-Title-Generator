"""
handlers/field_008.py
Builds and validates the MARC21 008 fixed-length data element for books (BK).

Note: Named field_008.py instead of 008.py because Python module names
cannot start with a digit.
"""
from datetime import datetime


# ── Reference tables (value → label) ────────────────────────────────────────

TYPE_OF_DATE_OPTIONS = [
    ("s", "s — Single known date/probable date"),
    ("m", "m — Multiple dates"),
    ("r", "r — Reprint/reissue date and original date"),
    ("t", "t — Publication date and copyright date"),
    ("q", "q — Questionable date"),
    ("n", "n — Dates unknown"),
    ("c", "c — Continuing resource currently published"),
    ("d", "d — Continuing resource ceased publication"),
    ("u", "u — Continuing resource status unknown"),
    ("e", "e — Detailed date"),
    ("i", "i — Inclusive dates of collection"),
    ("k", "k — Range of years of bulk of collection"),
    ("p", "p — Distribution/release date differs from production"),
    ("b", "b — No dates given; B.C. date involved"),
    ("|", "| — No attempt to code"),
]

ILLUSTRATION_OPTIONS = [
    ("a", "a — Illustrations"),
    ("b", "b — Maps"),
    ("c", "c — Portraits"),
    ("d", "d — Charts"),
    ("e", "e — Plans"),
    ("f", "f — Plates"),
    ("g", "g — Music"),
    ("h", "h — Facsimiles"),
    ("i", "i — Coats of arms"),
    ("j", "j — Genealogical tables"),
    ("k", "k — Forms"),
    ("l", "l — Samples"),
    ("m", "m — Phonodisc/phonowire"),
    ("o", "o — Photographs"),
    ("p", "p — Illuminations"),
]

TARGET_AUDIENCE_OPTIONS = [
    (" ", "  — Unknown or not specified"),
    ("a", "a — Preschool"),
    ("b", "b — Primary"),
    ("c", "c — Pre-adolescent"),
    ("d", "d — Adolescent"),
    ("e", "e — Adult"),
    ("f", "f — Specialized"),
    ("g", "g — General"),
    ("j", "j — Juvenile"),
    ("|", "| — No attempt to code"),
]

FORM_OF_ITEM_OPTIONS = [
    (" ", "  — None of the following"),
    ("a", "a — Microfilm"),
    ("b", "b — Microfiche"),
    ("c", "c — Microopaque"),
    ("d", "d — Large print"),
    ("e", "e — Newspaper format"),
    ("f", "f — Braille"),
    ("o", "o — Online"),
    ("q", "q — Direct electronic"),
    ("r", "r — Regular print reproduction"),
    ("s", "s — Electronic"),
    ("|", "| — No attempt to code"),
]

NATURE_OF_CONTENTS_OPTIONS = [
    ("a", "a — Abstracts/summaries"),
    ("b", "b — Bibliographies"),
    ("c", "c — Catalogs"),
    ("d", "d — Dictionaries"),
    ("e", "e — Encyclopedias"),
    ("f", "f — Handbooks"),
    ("g", "g — Legal articles"),
    ("i", "i — Indexes"),
    ("j", "j — Patent documents"),
    ("k", "k — Discographies"),
    ("l", "l — Legislation"),
    ("m", "m — Theses/dissertations"),
    ("n", "n — Surveys of literature"),
    ("o", "o — Reviews"),
    ("p", "p — Programmed texts"),
    ("q", "q — Filmographies"),
    ("r", "r — Directories"),
    ("s", "s — Statistics"),
    ("t", "t — Technical reports"),
    ("u", "u — Standards/specifications"),
    ("v", "v — Legal cases and notes"),
    ("w", "w — Law reports and digests"),
    ("y", "y — Yearbooks"),
    ("z", "z — Treaties"),
    ("2", "2 — Offprints"),
    ("5", "5 — Calendars"),
    ("6", "6 — Comics/graphic novels"),
]

GOVERNMENT_PUBLICATION_OPTIONS = [
    (" ", "  — Not a government publication"),
    ("a", "a — Autonomous or semi-autonomous body"),
    ("c", "c — Multilocal"),
    ("f", "f — Federal/national"),
    ("i", "i — International intergovernmental"),
    ("l", "l — Local"),
    ("m", "m — Multistate"),
    ("o", "o — Government publication (level unspecified)"),
    ("s", "s — State, provincial, territorial, dependent, etc."),
    ("u", "u — Unknown if government publication"),
    ("z", "z — Other"),
    ("|", "| — No attempt to code"),
]

CONFERENCE_PUBLICATION_OPTIONS = [
    ("0", "0 — Not a conference publication"),
    ("1", "1 — Conference publication"),
    ("|", "| — No attempt to code"),
]

FESTSCHRIFT_OPTIONS = [
    ("0", "0 — Not a festschrift"),
    ("1", "1 — Festschrift"),
    ("|", "| — No attempt to code"),
]

INDEX_OPTIONS = [
    ("0", "0 — No index"),
    ("1", "1 — Index present"),
    ("|", "| — No attempt to code"),
]

LITERARY_FORM_OPTIONS = [
    ("0", "0 — Not fiction"),
    ("1", "1 — Fiction"),
    ("d", "d — Dramas"),
    ("e", "e — Essays"),
    ("f", "f — Novels"),
    ("h", "h — Humor, satire"),
    ("i", "i — Letters"),
    ("j", "j — Short stories"),
    ("m", "m — Mixed forms"),
    ("p", "p — Poetry"),
    ("s", "s — Speeches"),
    ("u", "u — Unknown"),
    ("|", "| — No attempt to code"),
]

BIOGRAPHY_OPTIONS = [
    (" ", "  — No biographical information"),
    ("a", "a — Autobiography"),
    ("b", "b — Individual biography"),
    ("c", "c — Collective biography"),
    ("d", "d — Contains biographical information"),
    ("|", "| — No attempt to code"),
]

MODIFIED_RECORD_OPTIONS = [
    (" ", "  — Not modified"),
    ("d", "d — Dashed-on information omitted"),
    ("o", "o — Completely romanized"),
    ("r", "r — Romanized"),
    ("s", "s — Shortened"),
    ("x", "x — Missing characters"),
    ("|", "| — No attempt to code"),
]

CATALOGING_SOURCE_OPTIONS = [
    ("d", "d — Other"),
    (" ", "  — National bibliographic agency"),
    ("c", "c — Cooperative cataloging program"),
    ("u", "u — Unknown"),
    ("|", "| — No attempt to code"),
]


def build_008(
    type_of_date='s',
    date1='',
    date2='    ',
    place='ne',
    illustrations=None,
    target_audience=' ',
    form_of_item=' ',
    nature_of_contents=None,
    government_pub=' ',
    conference_pub='0',
    festschrift='0',
    index='0',
    literary_form='0',
    biography=' ',
    language='dut',
    modified_record=' ',
    cataloging_source='d'
):
    """
    Build a valid 40-character MARC21 008 field for books (LDR/06=a, 07=m).
    All inputs are validated and padded to the correct positional lengths.

    Position map:
      00-05  Date entered on file (auto: today YYMMDD)
      06     Type of date
      07-10  Date 1
      11-14  Date 2
      15-17  Place of publication
      18-21  Illustrations (up to 4 codes, space-padded)
      22     Target audience
      23     Form of item
      24-27  Nature of contents (up to 4 codes, space-padded)
      28     Government publication
      29     Conference publication
      30     Festschrift
      31     Index
      32     Undefined (always blank)
      33     Literary form
      34     Biography
      35-37  Language
      38     Modified record
      39     Cataloging source
    """
    today = datetime.now().strftime('%y%m%d')          # pos 00-05  (6)

    tod = (str(type_of_date) or 's')[:1]               # pos 06     (1)

    d1 = str(date1).strip()
    if not (d1.isdigit() and len(d1) == 4):
        d1 = str(datetime.now().year)
    date1_clean = d1[:4]                               # pos 07-10  (4)

    date2_clean = str(date2 or '    ').ljust(4)[:4]    # pos 11-14  (4)

    place_clean = str(place or 'ne').strip().ljust(3)[:3]  # pos 15-17 (3)

    ill_list = illustrations if isinstance(illustrations, list) else []
    ill_str = ''.join(c for c in ill_list[:4] if len(c) == 1).ljust(4)[:4]  # 18-21 (4)

    ta  = (str(target_audience or ' '))[:1]            # pos 22     (1)
    foi = (str(form_of_item or ' '))[:1]               # pos 23     (1)

    noc_list = nature_of_contents if isinstance(nature_of_contents, list) else []
    noc_str = ''.join(c for c in noc_list[:4] if len(c) == 1).ljust(4)[:4]  # 24-27 (4)

    gov  = (str(government_pub or ' '))[:1]            # pos 28     (1)
    conf = (str(conference_pub or '0'))[:1]            # pos 29     (1)
    fest = (str(festschrift or '0'))[:1]               # pos 30     (1)
    idx  = (str(index or '0'))[:1]                     # pos 31     (1)
    undef = ' '                                        # pos 32     (1)
    lit  = (str(literary_form or '0'))[:1]             # pos 33     (1)
    bio  = (str(biography or ' '))[:1]                 # pos 34     (1)
    lang = str(language or 'und').strip().ljust(3)[:3] # pos 35-37  (3)
    mod  = (str(modified_record or ' '))[:1]           # pos 38     (1)
    src  = (str(cataloging_source or 'd'))[:1]         # pos 39     (1)

    field = (
        today + tod + date1_clean + date2_clean +
        place_clean + ill_str + ta + foi + noc_str +
        gov + conf + fest + idx + undef +
        lit + bio + lang + mod + src
    )

    if len(field) != 40:
        raise ValueError(f"008 construction error: got {len(field)} chars, expected 40")

    return field
