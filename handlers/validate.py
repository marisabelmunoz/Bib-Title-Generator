"""MARC21 XML Validator — uses static/marcrules.txt and static/rda_types.json
Checks: XML well-formedness, namespace, record structure, leader,
        control fields, data fields, indicators, subfield codes,
        delimiter characters, whitespace anomalies, encoding,
        rules from marcrules.txt, and RDA 336/337/338 consistency.
"""

import os
import re
import json
import unicodedata
from pathlib import Path
from lxml import etree
import requests

# Use relative import first (module lives alongside oclc_api.py / config.py),
# fall back to absolute import for other execution environments.
try:
    from .oclc_api import get_access_token, get_user_agent
    from .config import load_credentials
except (ImportError, ValueError):
    from oclc_api import get_access_token, get_user_agent
    from config import load_credentials

# Paths
RULES_FILE = Path(__file__).parent.parent / "static" / "marcrules.txt"
RDA_FILE = Path(__file__).parent.parent / "static" / "rda_types.json"

# Namespace
MARC_NS = "http://www.loc.gov/MARC21/slim"

# OCLC "Validate a Bibliographic Record" endpoint
# POST /worldcat/manage/bibs/validate/{validationLevel}
OCLC_VALIDATE_BASE = "https://metadata.api.oclc.org/worldcat/manage/bibs/validate"
OCLC_VALIDATION_LEVELS = {"validateFull", "validateAdd", "validateReplace"}

# Leader definitions
LEADER_LENGTH = 24
LEADER_VALID_STATUS = set("acdnp")
LEADER_VALID_TYPE = set("acdefgijkmoprt")
LEADER_VALID_BIBLEVEL = set("abcdims")
LEADER_VALID_CTRL = set(" a")
LEADER_VALID_ENC = set("a")
LEADER_VALID_INDCOUNT = set("2")
LEADER_VALID_SUBFCOUNT = set("2")

# Control field tags
CONTROL_FIELD_TAGS = {"001", "003", "005", "006", "007", "008", "009"}

# Regex
RE_FIELD_TAG = re.compile(r"^\d{3}$")
RE_SUBFCODE = re.compile(r"^[a-z0-9]$")
RE_IND = re.compile(r"^[ 0-9a-z#]$")
RE_CTRL_NUM = re.compile(r"^\S+$")

# OCLC required/recommended (still used)
OCLC_REQUIRED_FIELDS = {"008", "040", "245"}
OCLC_RECOMMENDED_FIELDS = {"020", "300", "336", "337", "338"}

# Language codes (brief)
VALID_LANG_CODES = {
    "eng", "fre", "ger", "spa", "ita", "dut", "rus", "lat",
    "jpn", "chi", "kor", "ara", "por", "swe", "nor", "dan",
    "fin", "pol", "hun", "cze", "rum", "tur", "heb", "gre",
    "vie", "ind", "may", "tha", "bul", "srp", "hrv", "slv",
}
VALID_DESCRIPTION_CONVENTIONS = {"rda", "aacr2", "dacs", "rad", "isbd"}


# ----------------------------------------------------------------------
# Load MARC rules from static/marcrules.txt
# ----------------------------------------------------------------------
def load_marc_rules(rules_path=RULES_FILE):
    if not rules_path.exists():
        return {"field_rules": {}, "control_lengths": {}, "special": {}}

    with open(rules_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    field_rules = {}
    control_lengths = {}
    current_tag = None
    current = None
    length_map_007 = {}

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue

        parts = line.split("\t")
        first = parts[0].strip()
        if re.match(r"^\d{3}$", first) or first in ("1xx", "2xx", "3xx", "4xx", "5xx", "6xx", "7xx", "8xx"):
            if current_tag and current:
                field_rules[current_tag] = current
            current_tag = first
            repeatability = parts[1].strip() if len(parts) > 1 else "R"
            repeatable = not (repeatability in ("1", "NR", "NR "))
            current = {
                "repeatable": repeatable,
                "ind1": {"allowed": set(), "desc": ""},
                "ind2": {"allowed": set(), "desc": ""},
                "subfields": {}
            }
            in_subfields = False
            i += 1
            continue

        if current_tag is None:
            i += 1
            continue

        if line.startswith("ind1"):
            if len(parts) >= 2:
                val_str = parts[1].strip()
                desc = parts[2].strip() if len(parts) > 2 else ""
                allowed = _parse_indicator_allowed(val_str)
                current["ind1"] = {"allowed": allowed, "desc": desc}
            i += 1
            continue
        if line.startswith("ind2"):
            if len(parts) >= 2:
                val_str = parts[1].strip()
                desc = parts[2].strip() if len(parts) > 2 else ""
                allowed = _parse_indicator_allowed(val_str)
                current["ind2"] = {"allowed": allowed, "desc": desc}
            i += 1
            continue

        if len(parts) >= 2 and re.match(r"^[a-z0-9]$", parts[0].strip()):
            code = parts[0].strip()
            repeat = parts[1].strip()
            repeatable = (repeat == "R")
            desc = parts[2].strip() if len(parts) > 2 else ""
            current["subfields"][code] = {"repeatable": repeatable, "desc": desc}
            i += 1
            continue

        if current_tag == "006" and line.strip().startswith("length"):
            if len(parts) >= 2:
                control_lengths["006"] = int(parts[1].strip())
        elif current_tag == "008" and line.strip().startswith("length"):
            if len(parts) >= 2:
                control_lengths["008"] = int(parts[1].strip())
        elif current_tag == "007" and line.strip().startswith("length"):
            if len(parts) >= 2:
                mapping_str = parts[1].strip()
                for pair in mapping_str.split(","):
                    if ":" not in pair:
                        continue
                    cat, lens = pair.split(":", 1)
                    if "|" in lens:
                        lengths = [int(x) for x in lens.split("|")]
                    else:
                        lengths = [int(lens)]
                    length_map_007[cat] = lengths
                control_lengths["007"] = length_map_007

        i += 1

    if current_tag and current:
        field_rules[current_tag] = current

    special = {"max_one_1xx": True, "require_245": True}
    return {"field_rules": field_rules, "control_lengths": control_lengths, "special": special}


def _parse_indicator_allowed(val_str):
    if not val_str or val_str == "blank":
        return {" "}
    allowed = set()
    if 'b' in val_str:
        allowed.add(' ')
    for ch in val_str:
        if ch.isdigit() or ch.isalpha():
            allowed.add(ch)
    return allowed


MARC_RULES = load_marc_rules()
FIELD_RULES = MARC_RULES.get("field_rules", {})
CONTROL_LENGTHS = MARC_RULES.get("control_lengths", {})
SPECIAL_RULES = MARC_RULES.get("special", {})


# ----------------------------------------------------------------------
# Load RDA types from static/rda_types.json
# ----------------------------------------------------------------------
def load_rda_data():
    if not RDA_FILE.exists():
        return {}
    with open(RDA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


RDA_DATA = load_rda_data()


def _normalize_term(term):
    """Lowercase and strip for comparison."""
    return term.lower().strip()


def _get_rda_entry(tag, term, lang):
    """Return the RDA entry for given tag and term in the specified language."""
    if tag not in RDA_DATA:
        return None
    lang_data = RDA_DATA[tag].get(lang, [])
    norm_term = _normalize_term(term)
    for entry in lang_data:
        if _normalize_term(entry.get("term", "")) == norm_term:
            return entry
    return None


# ----------------------------------------------------------------------
# OCLC "Validate a Bibliographic Record" API
# ----------------------------------------------------------------------
def _resolve_credentials():
    """
    Normalise whatever load_credentials() returns into (client_id, client_secret).
    Supports a dict with 'client_id'/'client_secret' keys, or a 2-item tuple/list.
    """
    creds = load_credentials()
    if isinstance(creds, dict):
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        if client_id and client_secret:
            return client_id, client_secret
        raise ValueError("load_credentials() dict is missing 'client_id'/'client_secret'.")
    if isinstance(creds, (list, tuple)) and len(creds) >= 2:
        return creds[0], creds[1]
    raise ValueError("Unrecognized credentials format returned by load_credentials().")


def _extract_oclc_field_messages(node, found=None):
    """
    OCLC's validate response can include a nested array of field-level notices,
    e.g. {"tag": "049", "errorLevel": "MINOR", "message": "1st $a in 049 is too short."},
    alongside the top-level {"status": {"summary": ..., "description": ...}}.
    This walks the payload looking for any dict that has both 'tag' and 'message'
    and collects them, regardless of which key they're nested under, since OCLC
    doesn't document a single stable location for this array.
    """
    if found is None:
        found = []
    if isinstance(node, dict):
        if "tag" in node and "message" in node:
            found.append({
                "tag": node.get("tag"),
                "level": node.get("errorLevel") or node.get("level") or node.get("severity"),
                "message": node.get("message"),
            })
        else:
            for value in node.values():
                _extract_oclc_field_messages(value, found)
    elif isinstance(node, list):
        for item in node:
            _extract_oclc_field_messages(item, found)
    return found


def _call_oclc_validate(marcxml, validation_level="validateFull"):
    """
    Calls OCLC's Validate a Bibliographic Record endpoint:
        POST /worldcat/manage/bibs/validate/{validationLevel}

    Body: the MARC XML record (application/marcxml+xml).
    Response (200/400): {"status": {"summary": ..., "description": ...}}

    Returns a dict:
        {
            "called": bool,          # True if a request actually reached OCLC
            "summary": str|None,     # e.g. "VALID", "BIB_LACKS_CONTROL_NUMBER"
            "description": str|None,
            "http_status": int|None,
            "error": str|None,       # set if credentials/token/transport failed
        }
    """
    result = {
        "called": False,
        "summary": None,
        "description": None,
        "http_status": None,
        "error": None,
        "raw_response": None,
        "field_messages": [],
    }

    if validation_level not in OCLC_VALIDATION_LEVELS:
        result["error"] = (
            f"Invalid validationLevel '{validation_level}'. "
            f"Must be one of: {sorted(OCLC_VALIDATION_LEVELS)}"
        )
        return result

    try:
        client_id, client_secret = _resolve_credentials()
    except Exception as exc:
        result["error"] = f"Could not load OCLC credentials: {exc}"
        print(f"[OCLC validate] {result['error']}")
        return result

    try:
        token, _info = get_access_token(client_id, client_secret)
    except Exception as exc:
        result["error"] = f"OCLC OAuth token request failed: {exc}"
        print(f"[OCLC validate] {result['error']}")
        return result

    url = f"{OCLC_VALIDATE_BASE}/{validation_level}"
    try:
        response = requests.post(
            url,
            data=marcxml.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/marcxml+xml",
                "Accept": "application/json",
                "User-Agent": get_user_agent(),
            },
            timeout=30,
        )
    except Exception as exc:
        result["error"] = f"OCLC validate request failed: {exc}"
        return result

    result["called"] = True
    result["http_status"] = response.status_code
    result["raw_response"] = response.text

    # Log to console/server logs so the actual OCLC response is visible while
    # debugging (e.g. in `flask run` / `python app.py` output), since the
    # Flask access log line alone only shows "POST /validate-marc 200 -".
    print(f"[OCLC validate/{validation_level}] HTTP {response.status_code}: {response.text}")

    try:
        payload = response.json()
    except ValueError:
        result["error"] = f"OCLC returned a non-JSON response (HTTP {response.status_code})."
        return result

    status = payload.get("status", {}) if isinstance(payload, dict) else {}
    result["summary"] = status.get("summary")
    result["description"] = status.get("description")
    result["field_messages"] = _extract_oclc_field_messages(payload)

    if response.status_code == 401:
        result["error"] = payload.get("message", "Unauthorized (401) — check OCLC credentials.")
    elif response.status_code == 403:
        result["error"] = payload.get("message", "Forbidden (403).")
    elif response.status_code == 406:
        result["error"] = payload.get("detail") or "Accept header not acceptable (406)."
    elif response.status_code >= 500:
        result["error"] = payload.get("detail") or payload.get("title") or "OCLC server error."
    # 200 (valid) and 400 (validation rejected, e.g. BIB_LACKS_CONTROL_NUMBER) are
    # normal validation outcomes, not transport errors — leave result["error"] as None
    # and let the caller interpret result["summary"]/result["description"].

    return result


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _tag(local):
    return f"{{{MARC_NS}}}{local}"

def _strip_ns(tag):
    return tag.replace(f"{{{MARC_NS}}}", "")

def _text(el):
    return (el.text or "").strip()

def _has_nonprintable(text):
    bad = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("C") and ch not in ("\n", "\r", "\t"):
            bad.append((hex(ord(ch)), unicodedata.name(ch, "UNKNOWN")))
    return bad

def _check_encoding_anomalies(text, location):
    issues = []
    if "\ufffd" in text:
        issues.append(("error", f"{location}: Contains Unicode replacement character U+FFFD"))
    for seq in ("\xe2\x80\x9c", "\xc3\xa9"):
        if seq in text:
            issues.append(("warn", f"{location}: Possible UTF-8 mojibake detected"))
            break
    for ch, name in [("\u200b", "ZERO WIDTH SPACE"), ("\ufeff", "BOM"), ("\u00ad", "SOFT HYPHEN")]:
        if ch in text:
            issues.append(("warn", f"{location}: Contains {name} (U+{ord(ch):04X})"))
    return issues

def _check_trailing_spaces(text, location, tag=None):
    issues = []
    if text != text.strip():
        issues.append(("warn", f"{location}: Leading/trailing whitespace found"))
    # Skip double‑space warning for leader, 008, and 006
    if tag in ("LDR", "008", "006"):
        return issues
    if "  " in text:
        issues.append(("warn", f"{location}: Double (or more) consecutive spaces found"))
    return issues


# ----------------------------------------------------------------------
# RDA validation
# ----------------------------------------------------------------------
def _validate_rda_fields(datafields, cat_lang, err, warn):
    """
    Validate 336, 337, 338 fields against rda_types.json.
    Uses cataloging language from 040 $b (cat_lang: 'eng' or 'dut').
    Checks:
      - $a term exists in the appropriate language.
      - $b code matches the entry's code (if present).
      - $2 source (full string) matches entry['source'] exactly.
    """
    for df in datafields:
        tag = df.get("tag", "").strip()
        if tag not in ("336", "337", "338"):
            continue

        subfields = df.findall(_tag("subfield"))
        codes = {sf.get("code", ""): (sf.text or "").strip() for sf in subfields}

        a_val = codes.get("a", "")
        b_val = codes.get("b", "")
        two_val = codes.get("2", "")

        if not a_val:
            err(f"tag {tag}: missing $a (content/media/carrier term).")
            continue

        # Look up term in the determined cataloging language
        entry = _get_rda_entry(tag, a_val, cat_lang)
        if not entry:
            # Try the other language
            other_lang = "dut" if cat_lang == "eng" else "eng"
            entry = _get_rda_entry(tag, a_val, other_lang)
            if entry:
                warn(f"tag {tag}: term '{a_val}' found in language '{other_lang}' but cataloging language is '{cat_lang}'. Please check 040 $b.")
            else:
                err(f"tag {tag}: term '{a_val}' not found in rda_types.json for language '{cat_lang}'.")
                continue

        expected_code = entry.get("code", "")
        expected_source = entry.get("source", "")

        # Check $b (code) if present
        if b_val:
            if b_val != expected_code:
                err(f"tag {tag}: $b '{b_val}' does not match expected code '{expected_code}' for term '{a_val}'.")

        # Check $2 source (full string should match entry['source'])
        if not two_val:
            warn(f"tag {tag}: missing $2 source. Expected '{expected_source}'.")
        elif two_val != expected_source:
            warn(f"tag {tag}: $2 '{two_val}' does not match expected '{expected_source}'. Did you mean '{expected_source}'?")
        # else: exact match, fine
# ----------------------------------------------------------------------
# Core validator
# ----------------------------------------------------------------------
def validate_marc_xml(xml_string, include_oclc=True, oclc_validation_level="validateFull"):
    """
    Validate a MARCXML string.

    Local checks (unchanged): XML well-formedness, namespace, record structure,
    leader, control fields, data fields, indicators, subfield codes, delimiter
    characters, whitespace anomalies, encoding, marcrules.txt rules, and RDA
    336/337/338 consistency.

    In addition, when include_oclc=True, each parsed <record> is also submitted
    to OCLC's own "Validate a Bibliographic Record" endpoint
    (POST /worldcat/manage/bibs/validate/{validationLevel}) and its verdict is
    merged into the same errors/warnings lists, plus reported per-record under
    results["oclc"].
    """
    results = {
        "errors":   [],
        "warnings": [],
        "info":     [],
        "records":  0,
        "valid":    False,
        "oclc":     [],
    }

    def err(msg):  results["errors"].append(msg)
    def warn(msg): results["warnings"].append(msg)
    def info(msg): results["info"].append(msg)

    raw = xml_string.strip()
    if not raw:
        err("Input is empty.")
        return results

    if raw.startswith("\ufeff"):
        warn("XML starts with BOM (U+FEFF). Remove it.")
        raw = raw.lstrip("\ufeff")

    try:
        parser = etree.XMLParser(recover=False, remove_comments=False,
                                 resolve_entities=False, ns_clean=True)
        tree = etree.fromstring(raw.encode("utf-8"), parser=parser)
    except etree.XMLSyntaxError as exc:
        line = getattr(exc, 'line', None)
        if line:
            err(f"XML syntax error on line {line}: {exc}")
        else:
            err(f"XML syntax error — not well-formed: {exc}")
        return results

    # Root and namespace
    root_local = _strip_ns(tree.tag)
    ns = tree.nsmap.get(None) or tree.nsmap.get("marc", "")

    if root_local == "collection":
        records = tree.findall(_tag("record"))
        if not records:
            records = tree.findall("record")
        if not records:
            warn("Root <collection> has no <record> children.")
    elif root_local == "record":
        records = [tree]
    else:
        err(f"Unexpected root element <{root_local}>. Expected <collection> or <record>.")
        return results

    if ns != MARC_NS:
        if ns:
            warn(f"Namespace is '{ns}' — expected '{MARC_NS}'.")
        else:
            warn("No MARC21/slim namespace declared.")

    results["records"] = len(records)

    # Validate each record
    for rec_idx, record in enumerate(records, start=1):
        prefix = f"Record {rec_idx}"  # kept only for internal use, not in final messages
        if record.text and record.text.strip():
            warn(f"{prefix}: Unexpected text content directly inside <record>.")

        children = list(record)

        # Leader
        leaders = [c for c in children if _strip_ns(c.tag) == "leader"]
        if not leaders:
            err(f"Leader missing.")
        elif len(leaders) > 1:
            err(f"Multiple <leader> elements.")
        else:
            _validate_leader(leaders[0], err, warn)

        # Control fields
        ctrlfields = [c for c in children if _strip_ns(c.tag) == "controlfield"]
        _validate_controlfields(ctrlfields, err, warn)

        # Data fields
        datafields = [c for c in children if _strip_ns(c.tag) == "datafield"]
        _validate_datafields(datafields, err, warn)

        # Determine cataloging language from 040 $b
        cat_lang = "eng"  # default
        for f040 in [df for df in datafields if df.get("tag", "") == "040"]:
            subfields = f040.findall(_tag("subfield"))
            codes = {sf.get("code", ""): _text(sf) for sf in subfields}
            lang_code = codes.get("b", "").lower()
            if lang_code in ("dut", "nl"):
                cat_lang = "dut"
                break
            # else keep EN

        # --- RDA validation (336,337,338) ---
        _validate_rda_fields(datafields, cat_lang, err, warn)

        # Unknown children
        known = {"leader", "controlfield", "datafield"}
        for child in children:
            local = _strip_ns(child.tag)
            if local not in known:
                warn(f"Unknown child element <{local}> inside <record>.")

        # OCLC field presence
        all_tags = set()
        for cf in ctrlfields:
            t = cf.get("tag", "").strip()
            if t:
                all_tags.add(t)
        for df in datafields:
            t = df.get("tag", "").strip()
            if t:
                all_tags.add(t)

        for t in sorted(OCLC_REQUIRED_FIELDS - all_tags):
            err(f"OCLC required field {t} is missing.")
        for t in sorted(OCLC_RECOMMENDED_FIELDS - all_tags):
            warn(f"OCLC recommended field {t} is absent.")

        # Non-repeatable checks
        tag_counts = {}
        for df in datafields:
            t = df.get("tag", "").strip()
            tag_counts[t] = tag_counts.get(t, 0) + 1
        for t, cnt in tag_counts.items():
            rule = FIELD_RULES.get(t)
            if rule and not rule["repeatable"] and cnt > 1:
                warn(f"tag {t}: non-repeatable but appears {cnt} times.")

        # Only one 1XX
        onexx_count = sum(tag_counts.get(t, 0) for t in ("100","110","111","130"))
        if onexx_count > 1:
            err(f"Only one 1XX main entry field allowed, found {onexx_count}.")
        elif onexx_count == 0:
            warn("No 1XX main entry field found.")

        # 245 required
        if "245" not in tag_counts:
            err("Field 245 (Title Statement) is required.")
        elif tag_counts["245"] > 1:
            err("Field 245 is non-repeatable but appears multiple times.")

        # 040 RDA check (additional)
        for f040 in [df for df in datafields if df.get("tag", "") == "040"]:
            subfields = list(f040.findall(_tag("subfield")))
            codes = {sf.get("code", ""): _text(sf) for sf in subfields}
            if "e" not in codes:
                warn("tag 040: missing $e (description conventions). Add $erda.")
            else:
                val = codes["e"].lower()
                if val not in VALID_DESCRIPTION_CONVENTIONS:
                    warn(f"tag 040 $e '{val}' not recognised.")
            if "b" in codes and codes["b"].lower() not in VALID_LANG_CODES:
                warn(f"tag 040 $b language code '{codes['b']}' not recognised.")

        # --- OCLC "Validate a Bibliographic Record" check ---
        # Runs in addition to (not instead of) the local RDA/MARC21 rules above.
        if include_oclc:
            try:
                record_xml = etree.tostring(record, encoding="utf-8").decode("utf-8")
            except Exception as exc:
                record_xml = None
                warn(f"Record {rec_idx}: could not serialize record for OCLC validation: {exc}")

            if record_xml:
                oclc_result = _call_oclc_validate(record_xml, oclc_validation_level)
                oclc_result["record"] = rec_idx
                results["oclc"].append(oclc_result)

                if oclc_result["error"]:
                    # Credentials / token / transport problem — don't fail the whole
                    # validation, just flag that the OCLC check itself didn't run.
                    warn(f"Record {rec_idx}: OCLC validation unavailable — {oclc_result['error']}")
                else:
                    overall_valid = (oclc_result["summary"] == "VALID")
                    field_msgs = oclc_result.get("field_messages") or []

                    for fm in field_msgs:
                        level = (fm.get("level") or "").upper()
                        fm_tag = fm.get("tag", "?")
                        fm_msg = fm.get("message", "")
                        text = f"tag {fm_tag}: {fm_msg} (OCLC)"
                        # A "VALID" overall summary means the record passed; any notices
                        # riding along with it (e.g. errorLevel "MINOR") are advisory only
                        # and must never flip the result to failed.
                        if overall_valid or level in ("MINOR", "WARNING", "WARN", "INFO"):
                            warn(text)
                        else:
                            err(text)

                    if overall_valid:
                        info(f"Record {rec_idx}: OCLC validation passed (VALID).")
                    elif oclc_result["summary"]:
                        # Only fall back to the generic description when OCLC didn't
                        # give us specific field-level messages to show instead.
                        if not field_msgs:
                            err(
                                f"Record {rec_idx}: OCLC validation failed — "
                                f"{oclc_result['description'] or oclc_result['summary']}"
                            )
                    elif oclc_result["called"]:
                        warn(
                            f"Record {rec_idx}: OCLC returned an unexpected response "
                            f"(HTTP {oclc_result['http_status']})."
                        )

    # Final summary
    e_count = len(results["errors"])
    w_count = len(results["warnings"])
    results["valid"] = (e_count == 0)
    return results


# ----------------------------------------------------------------------
# Internal validators (leader, controlfield, datafield)
# ----------------------------------------------------------------------
def _validate_leader(leader_el, err, warn):
    text = leader_el.text or ""

    if leader_el.attrib:
        warn("<leader> should have no attributes.")

    if len(text) != LEADER_LENGTH:
        err(f"Leader must be {LEADER_LENGTH} chars. Got {len(text)}.")
        return

    bad = _has_nonprintable(text)
    for code, name in bad:
        err(f"Leader: Non-printable character {code} ({name}) in leader.")

    pos05 = text[5]
    if pos05 not in LEADER_VALID_STATUS:
        warn(f"Leader pos 05 record status '{pos05}' not in {sorted(LEADER_VALID_STATUS)}.")
    pos06 = text[6]
    if pos06 not in LEADER_VALID_TYPE:
        err(f"Leader pos 06 type of record '{pos06}' not in {sorted(LEADER_VALID_TYPE)}.")
    pos07 = text[7]
    if pos07 not in LEADER_VALID_BIBLEVEL:
        err(f"Leader pos 07 bibliographic level '{pos07}' not in {sorted(LEADER_VALID_BIBLEVEL)}.")
    pos08 = text[8]
    if pos08 not in LEADER_VALID_CTRL:
        warn(f"Leader pos 08 type of control '{pos08}' should be space or 'a'.")
    pos09 = text[9]
    if pos09 != "a":
        err(f"Leader pos 09 character coding scheme must be 'a' (Unicode). Got '{pos09}'.")
    pos10 = text[10]
    if pos10 != "2":
        err(f"Leader pos 10 indicator count must be '2'. Got '{pos10}'.")
    pos11 = text[11]
    if pos11 != "2":
        err(f"Leader pos 11 subfield code count must be '2'. Got '{pos11}'.")
    base = text[12:17]
    if not base.isdigit():
        err(f"Leader pos 12-16 base address must be numeric. Got '{base}'.")
    pos17 = text[17]
    if pos17 not in set(" 1234578u"):
        warn(f"Leader pos 17 encoding level '{pos17}' unusual.")
    pos18 = text[18]
    if pos18 not in set(" acipu"):
        warn(f"Leader pos 18 descriptive cataloging form '{pos18}' unusual.")


def _validate_controlfields(ctrlfields, err, warn):
    seen = {}
    for cf in ctrlfields:
        loc_tag = cf.get("tag", "").strip()
        if not loc_tag:
            err("<controlfield> missing 'tag' attribute.")
            continue
        if not RE_FIELD_TAG.match(loc_tag):
            err(f"tag {loc_tag}: invalid tag (must be 3 digits).")
            continue
        if not loc_tag.startswith("00"):
            err(f"tag {loc_tag}: controlfield tags must be in 00X range.")
        if cf.findall(_tag("subfield")):
            err(f"tag {loc_tag}: <controlfield> must NOT contain <subfield> elements.")
        extra = set(cf.attrib.keys()) - {"tag"}
        if extra:
            warn(f"tag {loc_tag}: unexpected attributes: {extra}.")
        text = cf.text or ""

        for sev, msg in _check_encoding_anomalies(text, f"tag {loc_tag}"):
            (err if sev == "error" else warn)(msg)
        for sev, msg in _check_trailing_spaces(text, f"tag {loc_tag}", tag=loc_tag):
            warn(msg)

        # Length checks
        if loc_tag == "006":
            exp = CONTROL_LENGTHS.get("006")
            if exp and len(text) != exp:
                err(f"tag 006 must be {exp} chars. Got {len(text)}.")
        elif loc_tag == "007":
            lens_map = CONTROL_LENGTHS.get("007")
            if lens_map and text:
                cat = text[0]
                if cat in lens_map and len(text) not in lens_map[cat]:
                    err(f"tag 007 length for '{cat}' must be {lens_map[cat]}. Got {len(text)}.")
        elif loc_tag == "008":
            exp = CONTROL_LENGTHS.get("008", 40)
            if len(text) != exp:
                err(f"tag 008 must be {exp} chars. Got {len(text)}.")
            else:
                # basic checks
                if text[6] not in set("bcdeikmnpqrstu| "):
                    warn(f"tag 008/06 type of date '{text[6]}' unusual.")
                lang = text[35:38].strip()
                if lang and lang.lower() not in VALID_LANG_CODES and lang != "|||":
                    warn(f"tag 008/35-37 language '{lang}' — verify.")
                if not text[15:18].strip():
                    warn("tag 008/15-17 country empty.")
        # Tag-specific
        if loc_tag == "001":
            if not text:
                err("tag 001 is empty.")
            elif not RE_CTRL_NUM.match(text):
                warn("tag 001 contains spaces.")
            if seen.get("001", 0) > 0:
                err("tag 001 non-repeatable but appears twice.")
        elif loc_tag == "003":
            if text and not text.startswith("OCoLC"):
                warn("tag 003 not OCoLC.")
        elif loc_tag == "005":
            if text and not re.match(r"^\d{14}\.\d$", text):
                warn("tag 005 should be YYYYMMDDHHMMSS.F")
        seen[loc_tag] = seen.get(loc_tag, 0) + 1


def _validate_datafields(datafields, err, warn):
    missing_subfields_tags = []   # collect tags that have no subfields

    for df in datafields:
        tag = df.get("tag", "").strip()
        ind1 = df.get("ind1", "")
        ind2 = df.get("ind2", "")

        if not tag:
            err("<datafield> missing 'tag'.")
            continue
        if not RE_FIELD_TAG.match(tag):
            err(f"tag {tag}: invalid tag (must be 3 digits).")
            continue
        if tag.startswith("00"):
            err(f"tag {tag}: should be controlfield, not datafield.")
        if "ind1" not in df.attrib:
            err(f"tag {tag}: missing ind1 attribute.")
        if "ind2" not in df.attrib:
            err(f"tag {tag}: missing ind2 attribute.")
        extra = set(df.attrib.keys()) - {"tag", "ind1", "ind2"}
        if extra:
            warn(f"tag {tag}: unexpected attributes: {extra}.")

        # Flag tags not covered by our local marcrules.txt reference. This is just
        # a "we don't have a local definition for this" notice — it does NOT mean
        # the tag is actually invalid (e.g. OCLC-specific tags like 019/029 are
        # valid but may be absent from marcrules.txt). OCLC's own validate
        # endpoint below is the authoritative check for field acceptability.
        if tag not in FIELD_RULES and tag[0] + "xx" not in FIELD_RULES:
            warn(f"tag {tag}: not found in local marcrules.txt reference — verify it is correct before submitting.")

        # Indicator rules
        rule = FIELD_RULES.get(tag)
        if rule:
            allowed1 = rule["ind1"]["allowed"]
            if allowed1 and ind1 not in allowed1:
                if ind1 == "#" and " " in allowed1:
                    warn(f"tag {tag}: ind1 uses '#', prefer space.")
                else:
                    err(f"tag {tag}: ind1 '{ind1}' not allowed; expected {sorted(allowed1)}.")
            allowed2 = rule["ind2"]["allowed"]
            if allowed2 and ind2 not in allowed2:
                if ind2 == "#" and " " in allowed2:
                    warn(f"tag {tag}: ind2 uses '#', prefer space.")
                else:
                    err(f"tag {tag}: ind2 '{ind2}' not allowed; expected {sorted(allowed2)}.")
        else:
            # basic indicator check
            for name, val in [("ind1", ind1), ("ind2", ind2)]:
                if len(val) != 1:
                    err(f"tag {tag}: {name} must be 1 char. Got '{val}'.")
                elif not RE_IND.match(val):
                    if val == "#":
                        warn(f"tag {tag}: {name} uses '#', use space.")
                    else:
                        err(f"tag {tag}: {name} '{val}' invalid (space/digit/lowercase).")

        # --- Subfield handling ---
        subfields = list(df.findall(_tag("subfield")))
        if not subfields:
            missing_subfields_tags.append(tag)
            # Skip subfield‑specific checks, but continue with extra checks
            # (extra checks may warn about missing required subfields)
        else:
            seen_subcodes = {}
            for sf in subfields:
                code = sf.get("code", "")
                text = sf.text or ""

                if not code:
                    err(f"tag {tag}: missing 'code' attribute.")
                elif len(code) != 1:
                    err(f"tag {tag} ${code}: code must be 1 char. Got '{code}'.")
                elif not RE_SUBFCODE.match(code):
                    if code == "$":
                        err(f"tag {tag}: subfield code '$' invalid (flat‑file artefact).")
                    else:
                        err(f"tag {tag} ${code}: code '{code}' invalid (a-z or 0-9).")

                if rule and code not in rule["subfields"]:
                    warn(f"tag {tag} ${code}: subfield code not defined for field {tag}.")

                if sf.tail and sf.tail.strip():
                    warn(f"tag {tag}: text between subfields: '{sf.tail.strip()[:40]}'")

                for sev, msg in _check_encoding_anomalies(text, f"tag {tag} ${code}"):
                    (err if sev == "error" else warn)(msg)
                for sev, msg in _check_trailing_spaces(text, f"tag {tag} ${code}", tag=tag):
                    warn(msg)

                bad = _has_nonprintable(text)
                for hexc, name in bad:
                    err(f"tag {tag} ${code}: Non-printable char {hexc} ({name}).")
                if tag not in ("856",) and "$" in text:
                    # A literal '$' immediately followed by a letter/digit (e.g. "$b", "$e", "$1")
                    # strongly suggests an un-converted MARC mnemonic delimiter got merged into
                    # this subfield's text instead of becoming a real <subfield> split. This kind
                    # of structural corruption is invisible to per-tag checks but can make OCLC's
                    # own parser reject the whole record with a generic "Bib is invalid" message
                    # that doesn't name a field — so treat this pattern as an error, not a warning.
                    delim_match = re.search(r"\$[a-z0-9]", text)
                    if delim_match:
                        err(
                            f"tag {tag} ${code}: contains embedded '{delim_match.group(0)}' — looks like "
                            f"an un-converted MARC subfield delimiter merged into this subfield's text "
                            f"(not a real <subfield> split). This is a likely cause of OCLC rejecting the "
                            f"whole record as invalid without naming a field."
                        )
                    else:
                        warn(f"tag {tag} ${code}: Contains '$' – possible flat‑file delimiter.")

                # Subfield repeatability
                if rule and code in rule["subfields"]:
                    if not rule["subfields"][code]["repeatable"]:
                        if code in seen_subcodes:
                            warn(f"tag {tag} ${code}: non‑repeatable subfield appears again.")
                seen_subcodes[code] = seen_subcodes.get(code, 0) + 1

        # Tag‑specific extra checks (still run even if no subfields)
        _extra_field_checks(tag, ind1, ind2, subfields, err, warn)

    # --- After processing all datafields, emit a single error for missing subfields ---
    if missing_subfields_tags:
        err(
            f"Fields without subfields: {', '.join(missing_subfields_tags)}. "
            f"Fix: change <record> to <record xmlns=\"{MARC_NS}\">"
        )


def _extra_field_checks(tag, ind1, ind2, subfields, err, warn):
    codes = {sf.get("code", ""): (sf.text or "").strip() for sf in subfields}
    if tag == "020":
        if "a" not in codes and "z" not in codes:
            warn(f"tag {tag}: should contain $a or $z.")
    elif tag == "245":
        if "a" not in codes:
            err(f"tag {tag}: missing $a (title proper).")
        if ind2 not in ("", " ") and not ind2.isdigit():
            warn(f"tag {tag}: ind2 non‑filing characters should be digit.")
    elif tag == "264":
        if ind2 not in ("0","1","2","3","4"):
            warn(f"tag {tag}: ind2 should be 0‑4.")
        if not any(k in codes for k in ("a","b","c")):
            warn(f"tag {tag}: has none of $a/$b/$c.")
    elif tag in ("336","337","338"):
        # $2 presence already checked in _validate_rda_fields
        pass
    elif tag == "856":
        url = codes.get("u", "")
        if url and not re.match(r"^https?://", url, re.I):
            warn(f"tag {tag}: $u does not look like HTTP/HTTPS URL.")