"""
handlers/field_LDR.py
Builds and validates the MARC21 LDR (Leader) data element for books (BK).
"""

# ── Reference tables (value → label) ────────────────────────────────────────

LDR_06 = [
    ("a", "a — Language material"),
    ("c", "c — Notated music"),
    ("d", "d — Manuscript notated music"),
    ("e", "e — Cartographic material"),
    ("f", "f — Manuscript cartographic material"),
    ("g", "g — Projected medium"),
    ("i", "i — Nonmusical sound recording"),
    ("j", "j — Musical sound recording"),
    ("k", "k — Two-dimensional nonprojected graphic"),
    ("m", "m — Computer file"),
    ("o", "o — Kit"),
    ("p", "p — Mixed materials"),
    ("r", "r — Three-dimensional artifact or naturally occurring object"),
    ("t", "t — Manuscript language material"),
]

# Allowed BLvl values per Type
type_to_blvl = {
    "a": ["a", "c", "d", "m"],          # Books (Language material)
    "t": ["a", "c", "d", "m"],          # Manuscript language material
    "c": ["a", "b", "c", "d", "i", "m", "s"],  # Notated music
    "d": ["a", "c", "d", "m"],          # Manuscript notated music
    "e": ["a", "b", "c", "d", "i", "m", "s"],  # Cartographic material
    "f": ["a", "c", "d", "m"],          # Manuscript cartographic material
    "g": ["a", "b", "c", "d", "i", "m", "s"],  # Projected medium
    "i": ["a", "b", "c", "d", "i", "m", "s"],  # Nonmusical sound recording
    "j": ["a", "b", "c", "d", "i", "m", "s"],  # Musical sound recording
    "k": ["a", "b", "c", "d", "i", "m", "s"],  # 2D nonprojected graphic
    "m": ["a", "b", "c", "d", "i", "m", "s"],  # Computer file
    "o": ["a", "b", "c", "d", "i", "m", "s"],  # Kit
    "p": ["c", "d"],                     # Mixed materials (only collection/subunit)
    "r": ["a", "b", "c", "d", "i", "m", "s"],  # 3D artifact
}

LDR_07 = [
    ("a", "a — Monographic component part"),
    ("b", "b — Serial component part"),
    ("c", "c — Collection"),
    ("d", "d — Subunit"),
    ("i", "i — Integrating resource"),
    ("m", "m — Monograph/Item"),
    ("s", "s — Serial"),
]

LDR_08 = [
    (" ", "  — no specified type of control"),
    ("a", "a — archival"),
]

LDR_17 = [
    (" ", "  — Full level"),
    ("1", "1 — Full level, material not examined"),
    ("2", "2 — Less-than-full level, material not examined"),
    ("3", "3 — Abbreviated level"),
    ("4", "4 — Core level (obsolete; do not create new records)"),
    ("5", "5 — Partial (preliminary) level"),
    ("7", "7 — Minimal level"),
    ("8", "8 — Prepublication level"),
    ("M", "M — Added from a batch process"),
]

LDR_18 = [
    (" ", "  — Non-ISBD"),
    ("a", "a — AACR2"),
    ("c", "c — ISBD punctuation omitted"),
    ("i", "i — ISBD"),
    ("n", "n — Non-ISBD punctuation omitted"),
    ("u", "u — Unknown"),
]

def build_LDR(   
    LDR_06='a',
    LDR_07='m',
    LDR_08=' ',
    LDR_17='7',
    LDR_18='u'
):
    # ── Validate Type ↔ BLvl ──────────────────────────────────────────
    if LDR_06 not in type_to_blvl:
        raise ValueError(f"Invalid LDR/06 Type code: '{LDR_06}'")
    allowed_blvl = type_to_blvl[LDR_06]
    if LDR_07 not in allowed_blvl:
        raise ValueError(
            f"Invalid combination: LDR/06='{LDR_06}' with LDR/07='{LDR_07}'. "
            f"Allowed BLvl codes: {', '.join(allowed_blvl)}"
        )

    # ── Build the leader ──────────────────────────────────────────────
    ldr = [
        '00000',     # 00-04
        'n',         # 05
        LDR_06,      # 06
        LDR_07,      # 07
        LDR_08,      # 08
        ' 2200000',  # 09-16
        LDR_17,      # 17
        LDR_18,      # 18
        ' 4500'      # 19-23
    ]

    field = ''.join(ldr)
    if len(field) != 24:
        raise ValueError(f"LDR construction error: got {len(field)} chars, expected 24")
    return field