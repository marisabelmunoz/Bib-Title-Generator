"""
EUR Metadata Services — MARC21 Cataloging Tool
Main application logic with ISBN, Format support, and full Configuration handling.
"""
import os
from flask import Flask, render_template, request, jsonify
from handlers.config import (
    load_credentials, 
    save_credentials, 
    credentials_exist, 
    load_institution_config, 
    save_institution_config
)
from handlers.oclc_api import get_access_token, create_bib_record
from handlers.prompt import build_prompt
import threading
import time
import webbrowser

app = Flask(__name__)

@app.route("/")
def index():
    """Renders the main cataloging interface with current institution settings."""
    inst = load_institution_config()
    return render_template("index.html", **inst)

@app.route("/config", methods=["GET"])
def config_page():
    """Displays the configuration page with current settings."""
    inst = load_institution_config()
    return render_template("config.html", **inst)

@app.route("/config/institution", methods=["POST"])
def config_institution():
    """Handles saving institution-specific settings (Name, Code, Contact)."""
    try:
        institution_name = request.form.get("institution_name", "").strip()
        institution_code = request.form.get("institution_code", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        contact_email = request.form.get("contact_email", "").strip()

        save_institution_config(
            institution_name, 
            institution_code, 
            contact_name, 
            contact_email
        )
        
        # Reload settings to confirm they saved
        inst = load_institution_config()
        return render_template("config.html", inst_message="Institution settings saved successfully.", **inst)
    except Exception as e:
        inst = load_institution_config()
        return render_template("config.html", inst_error=f"Failed to save settings: {e}", **inst)

@app.route("/config/credentials", methods=["POST"])
def config_credentials():
    """Handles saving and encrypting OCLC API credentials."""
    client_id = request.form.get("client_id", "").strip()
    client_secret = request.form.get("client_secret", "").strip()
    
    inst = load_institution_config()

    if not client_id or not client_secret:
        return render_template("config.html", error="OCLC Client ID and Secret are required.", **inst)
    
    try:
        save_credentials(client_id, client_secret)
        return render_template("config.html", message="Credentials saved and encrypted successfully.", **inst)
    except Exception as e:
        return render_template("config.html", error=f"Failed to save credentials: {e}", **inst)

@app.route("/generate-prompt", methods=["POST"])
def generate_prompt():
    """Extracts metadata from request and builds the AI prompt."""
    data = request.get_json()
    
    # Extract metadata fields
    biography = data.get("biography", " ")
    index_val = data.get("index", "0")
    year = data.get("year", "")
    place = data.get("place", "ne")
    isbn = data.get("isbn", "").strip()
    format_book = data.get("format_book", "").strip()
    description = data.get("description", "")
    cat_lang = data.get("cat_lang", "eng")
    extra_instructions=data.get('extra_instructions', "")
    
    # Build the prompt using the handler
    prompt_text = build_prompt(
        biography, 
        index_val, 
        year, 
        place, 
        description, 
        isbn, 
        format_book,
        cat_lang,
        extra_instructions
    )
    
    return jsonify({"prompt": prompt_text})

@app.route("/submit-marc", methods=["POST"])
def submit_marc():
    """Submits the AI-generated MARCXML to OCLC WorldCat."""
    data = request.get_json()
    marcxml = data.get("marcxml")

    if not credentials_exist():
        return jsonify({"error": "OCLC credentials not configured."}), 400

    try:
        # Load encrypted credentials and get OAuth token
        creds = load_credentials()
        token, _ = get_access_token(creds["client_id"], creds["client_secret"])
        
        # Submit to OCLC
        response_text, status_code, _ = create_bib_record(marcxml, token)
        
        if status_code in (200, 201):
            import re
            # Extract OCLC Number (OCN) from the XML response
            ocn_match = re.search(r'<controlfield tag="001">on?(\d+)</controlfield>', response_text)
            ocn = ocn_match.group(1) if ocn_match else "Unknown"
            
            return jsonify({
                "ocn": ocn, 
                "edit_url": f"https://eur.share.worldcat.org/wms/cmnd/metadata/cataloging/edit/bib/{ocn}"
            })
        
        return jsonify({
            "error": f"OCLC Error {status_code}", 
            "detail": response_text[:500]
        }), 400
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/about")
def about():
    return render_template("about.html")

def open_browser():
    time.sleep(1.5) 
    webbrowser.open('http://127.0.0.1:5555')

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") is None:
        threading.Thread(target=open_browser, daemon=True).start()

    app.run(debug=True, host='127.0.0.1', port=5555)