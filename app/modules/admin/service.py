from ...models.app_config import AppConfig

ALLOWED_KEYS = {
    "upiId":            "UPI ID (e.g. committee@upi)",
    "orgName":          "Organisation name shown on QR and receipts",
    "contactPhone":     "Public contact phone number",
    "contactEmail":     "Public contact email address",
    "contactWhatsapp":  "Public WhatsApp number",
    "socialFacebook":   "Facebook page URL",
    "socialInstagram":  "Instagram profile URL",
    "socialYoutube":    "YouTube channel URL",
}

# maps camelCase payload key → internal DB key
_KEY_MAP = {
    "upiId":           "upi_id",
    "orgName":         "org_name",
    "contactPhone":    "contact.phone",
    "contactEmail":    "contact.email",
    "contactWhatsapp": "contact.whatsapp",
    "socialFacebook":  "social.facebook",
    "socialInstagram": "social.instagram",
    "socialYoutube":   "social.youtube",
}


def get_all() -> dict:
    rows = AppConfig.query.all()
    return {row.key: row.value for row in rows}


def set_keys(payload: dict) -> tuple[dict, dict]:
    """Set one or more config keys. Returns (updated, errors)."""
    updated, errors = {}, {}
    for key, value in payload.items():
        if key not in ALLOWED_KEYS:
            errors[key] = f"unknown key — allowed: {list(ALLOWED_KEYS)}"
            continue
        db_key = _KEY_MAP[key]
        AppConfig.set(db_key, str(value).strip())
        updated[key] = str(value).strip()
    return updated, errors
