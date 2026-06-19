"""
MARCXML Preview — human‑readable field listing
"""

from lxml import etree

MARC_NS = "http://www.loc.gov/MARC21/slim"

def _tag(local):
    return f"{{{MARC_NS}}}{local}"

def _strip_ns(tag):
    return tag.replace(f"{{{MARC_NS}}}", "")

def preview_marc_xml(xml_string):
    """Return a list of field entries with human-readable representation."""
    try:
        parser = etree.XMLParser(recover=True, remove_comments=False)
        tree = etree.fromstring(xml_string.encode("utf-8"), parser=parser)
    except etree.XMLSyntaxError as e:
        return {"error": f"XML not well‑formed: {e}"}

    root_local = _strip_ns(tree.tag)
    if root_local == "collection":
        records = tree.findall(_tag("record"))
        if not records:
            records = tree.findall("record")
        if not records:
            return {"error": "No <record> found inside <collection>."}
    elif root_local == "record":
        records = [tree]
    else:
        return {"error": f"Unexpected root element: {root_local}. Expected <record> or <collection>."}

    preview = []
    for rec_idx, record in enumerate(records, 1):
        rec_data = {"record": rec_idx, "fields": []}
        for child in record:
            tag_local = _strip_ns(child.tag)
            if tag_local == "leader":
                leader_text = (child.text or "").strip()
                rec_data["fields"].append({
                    "tag": "LEADER",
                    "indicators": "",
                    "subfields": [{"code": "", "value": leader_text}]
                })
            elif tag_local == "controlfield":
                tag = child.get("tag", "").strip()
                value = (child.text or "").strip()
                rec_data["fields"].append({
                    "tag": tag,
                    "indicators": "",
                    "subfields": [{"code": "", "value": value}]
                })
            elif tag_local == "datafield":
                tag = child.get("tag", "").strip()
                ind1 = child.get("ind1", " ")
                ind2 = child.get("ind2", " ")
                subfields = []
                for sf in child.findall(_tag("subfield")):
                    code = sf.get("code", "")
                    val = (sf.text or "").strip()
                    subfields.append({"code": code, "value": val})
                rec_data["fields"].append({
                    "tag": tag,
                    "indicators": f"{ind1}{ind2}",
                    "subfields": subfields
                })
        preview.append(rec_data)

    return {"preview": preview}