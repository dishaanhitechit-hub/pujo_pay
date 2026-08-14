from ...models.app_config import AppConfig

ALLOWED_KEYS = {
    "upi_id": "UPI ID (e.g. committee@upi)",
    "org_name": "Organisation name shown on QR and receipts",
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
        AppConfig.set(key, str(value).strip())
        updated[key] = str(value).strip()
    return updated, errors
