import base64
from pathlib import Path
from cryptography.fernet import Fernet

# Since this file is in /handlers/, we go up one level to reach the root, then into /data/
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "static" / "data"
CREDENTIALS_FILE = DATA_DIR / "credentials.txt"
INSTITUTION_CONFIG_FILE = DATA_DIR / "institution_config.txt"
CUSTOM_PROMPTS_FILE = DATA_DIR / "custom_prompts.txt"

# This key must remain the same to decrypt existing credentials
SECRET_KEY = b'pL9xW8_vG3R2k0_N7mB4v_C6xZ1lK9jH8gF7dS5aQ4w=' 

# Default values
DEFAULT_INSTITUTION_NAME = "Institution Name"
DEFAULT_INSTITUTION_CODE = "XXX"
DEFAULT_CONTACT_NAME = "Staff Name"
DEFAULT_CONTACT_EMAIL = "staff@email.com"

def credentials_exist() -> bool:
    """Checks if the credentials file exists on disk."""
    return CREDENTIALS_FILE.exists()

def save_credentials(client_id: str, client_secret: str) -> None:
    """Encrypt and save OCLC credentials."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    plaintext = f"{client_id}\n{client_secret}".encode("utf-8")
    f = Fernet(SECRET_KEY)
    encrypted = f.encrypt(plaintext)
    CREDENTIALS_FILE.write_bytes(encrypted)

def load_credentials() -> dict:
    """Decrypt and return OCLC credentials."""
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError("OCLC Credentials not configured.")
    
    f = Fernet(SECRET_KEY)
    try:
        decrypted = f.decrypt(CREDENTIALS_FILE.read_bytes())
        lines = decrypted.decode("utf-8").strip().splitlines()
        return {
            "client_id": lines[0].strip(),
            "client_secret": lines[1].strip()
        }
    except Exception as e:
        raise ValueError(f"Could not decrypt credentials. Please re-configure in settings. Error: {e}")

def save_institution_config(institution_name: str, institution_code: str, contact_name: str, contact_email: str) -> None:
    """Save institution configuration to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    content = f"{institution_name}\n{institution_code}\n{contact_name}\n{contact_email}"
    INSTITUTION_CONFIG_FILE.write_text(content, encoding="utf-8")

def load_institution_config() -> dict:
    """Load institution configuration from file."""
    if not INSTITUTION_CONFIG_FILE.exists():
        return {
            "institution_name": DEFAULT_INSTITUTION_NAME,
            "institution_code": DEFAULT_INSTITUTION_CODE,
            "contact_name": DEFAULT_CONTACT_NAME,
            "contact_email": DEFAULT_CONTACT_EMAIL
        }
    
    try:
        lines = INSTITUTION_CONFIG_FILE.read_text(encoding="utf-8").strip().splitlines()
        return {
            "institution_name": lines[0].strip() if len(lines) > 0 else DEFAULT_INSTITUTION_NAME,
            "institution_code": lines[1].strip() if len(lines) > 1 else DEFAULT_INSTITUTION_CODE,
            "contact_name": lines[2].strip() if len(lines) > 2 else DEFAULT_CONTACT_NAME,
            "contact_email": lines[3].strip() if len(lines) > 3 else DEFAULT_CONTACT_EMAIL
        }
    except Exception:
        return {
            "institution_name": DEFAULT_INSTITUTION_NAME,
            "institution_code": DEFAULT_INSTITUTION_CODE,
            "contact_name": DEFAULT_CONTACT_NAME,
            "contact_email": DEFAULT_CONTACT_EMAIL
        }
    


def load_custom_prompts() -> list:
    """Load custom prompts from file. Returns list of {name, text} dicts."""
    if not CUSTOM_PROMPTS_FILE.exists():
        return []
    prompts = []
    for line in CUSTOM_PROMPTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "|||" in line:
            name, _, text = line.partition("|||")
            name = name.strip()
            text = text.strip()
            if name and text:
                prompts.append({"name": name, "text": text})
    return prompts


def save_custom_prompts(prompts: list) -> None:
    """Persist the full list of custom prompts to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"{p['name']}|||{p['text']}" for p in prompts]
    CUSTOM_PROMPTS_FILE.write_text("\n".join(lines), encoding="utf-8")


def add_custom_prompt(name: str, text: str) -> list:
    """Add or update a prompt by name. Returns the updated list."""
    prompts = load_custom_prompts()
    prompts = [p for p in prompts if p["name"].lower() != name.lower()]
    prompts.append({"name": name, "text": text})
    save_custom_prompts(prompts)
    return prompts


def delete_custom_prompt(name: str) -> list:
    """Delete a prompt by name. Returns the updated list."""
    prompts = [p for p in load_custom_prompts() if p["name"].lower() != name.lower()]
    save_custom_prompts(prompts)
    return prompts
