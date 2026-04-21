"""
EUR Metadata Services — OCLC API Module
Handles OAuth token retrieval and MARC record GET/PUT/CREATE operations.
"""

import re
import requests
from pathlib import Path

# Use a relative import since config.py is in the same 'handlers' folder
try:
    from .config import load_institution_config, load_credentials
except (ImportError, ValueError):
    # Fallback for different execution environments
    from config import load_institution_config, load_credentials

OCLC_TOKEN_URL = "https://oauth.oclc.org/token"
OCLC_API_BASE = "https://metadata.api.oclc.org/worldcat/manage/bibs"

def sanitize_marcxml(marcxml: str) -> str:
    """
    Sanitizes the MARCXML string by replacing non-breaking spaces (U+00A0) 
    with standard ASCII spaces (U+0020). This ensures fixed-field lengths 
    (like the 008) are calculated correctly by the OCLC validator.
    """
    if not marcxml:
        return marcxml
    # Replace Unicode non-breaking space with standard space
    return marcxml.replace("\u00a0", " ")

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
    GET a bibliographic MARC record by OCN.
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
    PUT (replace) a bibliographic MARC record by OCN.
    Automatically sanitizes whitespace before sending.
    """
    sanitized_xml = sanitize_marcxml(marcxml)
    url = f"{OCLC_API_BASE}/{ocn}"
    response = requests.put(
        url,
        data=sanitized_xml.encode("utf-8"),
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
    Automatically sanitizes whitespace before sending.
    """
    sanitized_xml = sanitize_marcxml(marcxml)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/marcxml+xml",
        "Accept": "application/marcxml+xml",
        "User-Agent": get_user_agent(),
    }
    
    try:
        response = requests.post(
            OCLC_API_BASE, 
            data=sanitized_xml.encode('utf-8'), 
            headers=headers, 
            timeout=30
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
    "tgn": "tgn", "ulan": "ulan"
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
        tag = term_data.get("field", "650")
        ind1 = term_data.get("ind1", " ")
        ind2 = term_data.get("ind2", "7")
        term_text = _escape_xml(term_data.get("term", ""))
        uri = _escape_xml(term_data.get("uri", ""))

        raw_source = term_data.get("source_label", "")
        source_label = _escape_xml(_normalise_source_code(raw_source))

        field_xml = (
            f'  <datafield tag="{tag}" ind1="{ind1}" ind2="{ind2}">\n'
            f'    <subfield code="a">{term_text}</subfield>\n'
            f'    <subfield code="2">{source_label}</subfield>\n'
        )
        
        if uri:
            field_xml += f'    <subfield code="1">{uri}</subfield>\n'
        
        field_xml += f"  </datafield>"
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