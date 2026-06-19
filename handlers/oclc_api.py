"""
EUR Metadata Services — OCLC API Module
Handles OAuth token retrieval and MARC record GET/PUT/CREATE operations.
Includes automatic addition of missing $b subfields for RDA fields 336,337,338.
"""

import re
import json
from pathlib import Path
from lxml import etree
import requests

# Use a relative import since config.py is in the same 'handlers' folder
try:
    from .config import load_institution_config, load_credentials
except (ImportError, ValueError):
    # Fallback for different execution environments
    from config import load_institution_config, load_credentials

OCLC_TOKEN_URL = "https://oauth.oclc.org/token"
OCLC_API_BASE  = "https://metadata.api.oclc.org/worldcat/manage/bibs"

# Namespace for MARC21
MARC_NS = "http://www.loc.gov/MARC21/slim"

# Path to rda_types.json
RDA_FILE = Path(__file__).parent.parent / "static" / "rda_types.json"

# Load RDA data once
def _load_rda_data():
    if not RDA_FILE.exists():
        return {}
    with open(RDA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

RDA_DATA = _load_rda_data()


def _normalize_term(term):
    """Lowercase and strip for comparison."""
    return term.lower().strip()


def _get_rda_entry(tag, term, lang="eng"):
    """Return the RDA entry for given tag and term in the specified language."""
    if tag not in RDA_DATA:
        return None
    lang_data = RDA_DATA[tag].get(lang, [])
    norm_term = _normalize_term(term)
    for entry in lang_data:
        if _normalize_term(entry.get("term", "")) == norm_term:
            return entry
    return None


def _determine_cataloging_language(marcxml):
    """Extract 040 $b from the MARCXML to determine cataloging language."""
    try:
        parser = etree.XMLParser(recover=False, resolve_entities=False)
        tree = etree.fromstring(marcxml.encode("utf-8"), parser=parser)
    except Exception:
        return "eng"  # default

    # Find 040 field
    for elem in tree.iter():
        if _strip_ns(elem.tag) == "datafield" and elem.get("tag") == "040":
            for sf in elem.findall(_tag("subfield")):
                if sf.get("code") == "b":
                    lang_code = (sf.text or "").strip().lower()
                    if lang_code in ("dut", "nl"):
                        return "dut"
    return "eng"


def _strip_ns(tag):
    return tag.replace(f"{{{MARC_NS}}}", "")


def _tag(local):
    return f"{{{MARC_NS}}}{local}"

def _add_missing_rda_subfield_b(marcxml):
    """
    Parse MARCXML and add missing $b subfields to 336,337,338 fields.
    Uses rda_types.json to look up the code based on $a and cataloging language.
    Inserts $b immediately after $a.
    """
    if not RDA_DATA:
        return marcxml

    try:
        parser = etree.XMLParser(recover=False, resolve_entities=False)
        tree = etree.fromstring(marcxml.encode("utf-8"), parser=parser)
    except Exception:
        return marcxml

    lang = _determine_cataloging_language(marcxml)
    modified = False

    for datafield in tree.iter():
        if _strip_ns(datafield.tag) != "datafield":
            continue
        tag = datafield.get("tag", "")
        if tag not in ("336", "337", "338"):
            continue

        # Collect subfields
        subfields = list(datafield.iterchildren(_tag("subfield")))
        if not subfields:
            continue

        # Check if $b already exists
        if any(sf.get("code") == "b" for sf in subfields):
            continue

        # Find the first $a subfield
        a_index = None
        a_subfield = None
        for i, sf in enumerate(subfields):
            if sf.get("code") == "a":
                a_index = i
                a_subfield = sf
                break

        if a_subfield is None:
            continue  # no $a, cannot determine code

        term = (a_subfield.text or "").strip()
        if not term:
            continue

        # Look up code
        entry = _get_rda_entry(tag, term, lang)
        if not entry:
            other_lang = "dut" if lang == "eng" else "eng"
            entry = _get_rda_entry(tag, term, other_lang)
        if not entry:
            continue

        code = entry.get("code")
        if not code:
            continue

        # Create $b subfield
        b_subfield = etree.SubElement(datafield, _tag("subfield"))
        b_subfield.set("code", "b")
        b_subfield.text = code

        # Move it to after $a
        if a_index is not None:
           datafield.insert(a_index + 1, b_subfield)

        modified = True

    if not modified:
        return marcxml

    return etree.tostring(tree, encoding="utf-8", pretty_print=True).decode("utf-8")


def sanitize_marcxml(marcxml: str) -> str:
    """
    Sanitizes the MARCXML string by replacing non-breaking spaces (U+00A0)
    with standard ASCII spaces (U+0020).  This ensures fixed-field lengths
    (like the 008) are calculated correctly by the OCLC validator.
    """
    if not marcxml:
        return marcxml
    return marcxml.replace("\u00a0", " ")


def prepare_marcxml_for_submission(marcxml: str) -> str:
    """
    Full preparation pipeline for MARCXML before sending to OCLC:
      1. Replace non-breaking spaces.
      2. Add missing $b subfields for RDA fields 336,337,338.
    """
    if not marcxml:
        return marcxml
    xml = sanitize_marcxml(marcxml)
    xml = _add_missing_rda_subfield_b(xml)
    return xml


def get_user_agent():
    """Get user agent string with current contact email."""
    inst_config = load_institution_config()
    return f"EUR Metadata Services Agent - contact: {inst_config['contact_email']}"


def get_access_token(client_id: str, client_secret: str) -> tuple[str, dict]:
    """
    Request an OAuth2 client_credentials token from OCLC.
    Returns (access_token, response_info_dict).
    """
    response = requests.post(
        OCLC_TOKEN_URL,
        data={"grant_type": "client_credentials", "scope": "WorldCatMetadataAPI"},
        auth=(client_id, client_secret),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": get_user_agent(),
        },
        timeout=20,
    )

    info = {
        "status_code": response.status_code,
        "raw_response": response.text,
    }

    if response.status_code != 200:
        raise RuntimeError(
            f"OAuth token request failed (HTTP {response.status_code}): {response.text}"
        )

    data = response.json()
    if "access_token" not in data:
        raise RuntimeError(f"No access_token in OAuth response: {data}")

    return data["access_token"], info


def get_bib_record(ocn: str, token: str) -> tuple[str, int, str]:
    """
    GET a bibliographic MARC record by OCN from WorldCat.

    Endpoint: GET /worldcat/manage/bibs/{oclcNumber}

    Returns (marcxml_string, http_status_code, raw_response_text).
    """
    url = f"{OCLC_API_BASE}/{ocn}"
    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/marcxml+xml",
            "User-Agent": get_user_agent(),
        },
        timeout=30,
    )
    return response.text, response.status_code, response.text


def put_bib_record(ocn: str, marcxml: str, token: str) -> tuple[str, int, str]:
    """
    PUT (replace) a bibliographic MARC record by OCN in WorldCat.

    Endpoint: PUT /worldcat/manage/bibs/{oclcNumber}

    If the record does not exist a new record will be created.
    Automatically prepares the MARCXML before sending.
    Returns (marcxml_string, http_status_code, raw_response_text).
    """
    prepared_xml = prepare_marcxml_for_submission(marcxml)
    url = f"{OCLC_API_BASE}/{ocn}"
    response = requests.put(
        url,
        data=prepared_xml.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/marcxml+xml",
            "Accept": "application/marcxml+xml",
            "User-Agent": get_user_agent(),
        },
        timeout=30,
    )
    return response.text, response.status_code, response.text


def create_bib_record(marcxml: str, token: str) -> tuple[str, int, str]:
    """
    Create a new bibliographic record in WorldCat.

    Endpoint: POST /worldcat/manage/bibs

    Automatically prepares the MARCXML before sending.
    Returns (marcxml_string, http_status_code, raw_response_text).
    """
    prepared_xml = prepare_marcxml_for_submission(marcxml)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/marcxml+xml",
        "Accept": "application/marcxml+xml",
        "User-Agent": get_user_agent(),
    }

    try:
        response = requests.post(
            OCLC_API_BASE,
            data=prepared_xml.encode("utf-8"),
            headers=headers,
            timeout=30,
        )
        return response.text, response.status_code, response.text
    except Exception as e:
        return str(e), 500, str(e)


def _escape_xml(text: str) -> str:
    """Escape special characters for XML content."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# Valid MARC $2 thesaurus codes accepted by OCLC WorldCat.
_VALID_SOURCE_CODES: dict[str, str] = {
    "aat": "aat", "gtt": "gtt", "fast": "fast", "lcsh": "lcsh",
    "mesh": "mesh", "ram": "ram", "rameau": "ram", "sears": "sears",
    "nlmnlm": "nlmnlm", "agrovoc": "agrovoc", "bkl": "bkl",
    "brinkman": "btr", "btr": "btr", "gtlvn": "gtlvn", "homoit": "homoit",
    "idsbb": "idsbb", "jurivoc": "jurivoc", "kiss": "kiss",
    "lacnaf": "lacnaf", "lcdgt": "lcdgt", "local": "local",
    "naf": "naf", "nta": "nta", "rero": "rero", "swd": "swd",
    "tgn": "tgn", "ulan": "ulan",
}


def _normalise_source_code(raw: str) -> str:
    """Map a caller-supplied vocabulary label to its canonical MARC $2 code."""
    key = raw.strip().lower()
    if key not in _VALID_SOURCE_CODES:
        raise ValueError(
            f"Unknown vocabulary source code: {raw!r}. "
            f"Must be one of: {sorted(_VALID_SOURCE_CODES)}"
        )
    return _VALID_SOURCE_CODES[key]


def add_terms_to_marcxml(marcxml: str, terms: list[dict]) -> str:
    """Insert new subject heading datafields into a MARC XML record string."""
    new_fields_parts = []
    for term_data in terms:
        tag       = term_data.get("field", "650")
        ind1      = term_data.get("ind1", " ")
        ind2      = term_data.get("ind2", "7")
        term_text = _escape_xml(term_data.get("term", ""))
        uri       = _escape_xml(term_data.get("uri", ""))

        raw_source   = term_data.get("source_label", "")
        source_label = _escape_xml(_normalise_source_code(raw_source))

        field_xml = (
            f'  <datafield tag="{tag}" ind1="{ind1}" ind2="{ind2}">\n'
            f'    <subfield code="a">{term_text}</subfield>\n'
            f'    <subfield code="2">{source_label}</subfield>\n'
        )

        if uri:
            field_xml += f'    <subfield code="1">{uri}</subfield>\n'

        field_xml += "  </datafield>"
        new_fields_parts.append(field_xml)

    if not new_fields_parts:
        return marcxml

    insertion = "\n".join(new_fields_parts) + "\n"

    modified, count = re.subn(
        r"(</(?:[\w]+:)?record>)",
        lambda m: insertion + m.group(1),
        marcxml,
        count=1,
    )

    if count == 0:
        modified = marcxml + "\n" + insertion

    return modified