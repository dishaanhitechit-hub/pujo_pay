from ...models.app_config import AppConfig

ALLOWED_KEYS = {
    "upiId":                  "UPI ID (e.g. committee@upi)",
    "orgName":                "Organisation name shown on QR and receipts",
    "contactPhone":           "Public contact phone number",
    "contactEmail":           "Public contact email address",
    "contactWhatsapp":        "Public WhatsApp number",
    "contactAddress":         "Public contact address",
    "supportTitle":           "Support section heading on the Contact page",
    "supportDescription":     "Support section body text on the Contact page",
    "supportWhatsappMessage": "Pre-filled WhatsApp message when a supporter taps the WhatsApp CTA",
    "socialFacebook":              "Facebook page URL",
    "socialInstagram":             "Instagram profile URL",
    "socialYoutube":               "YouTube channel URL",
    # Contribution payment details
    "contributionUpiId":           "UPI ID for member contributions (e.g. club@upi)",
    "contributionBankName":        "Bank name (e.g. State Bank of India)",
    "contributionAccountName":     "Account holder name",
    "contributionAccountNumber":   "Bank account number",
    "contributionIfsc":            "IFSC code",
    "contributionBankBranch":      "Branch name",
    # Platform-level registration payment
    "platformRegistrationUpiId":   "UPI ID shown on the Register Organisation page for payment",
}

# maps camelCase payload key → internal DB key
_KEY_MAP = {
    "upiId":                  "upi_id",
    "orgName":                "org_name",
    "contactPhone":           "contact.phone",
    "contactEmail":           "contact.email",
    "contactWhatsapp":        "contact.whatsapp",
    "contactAddress":         "contact.address",
    "supportTitle":           "support.title",
    "supportDescription":     "support.description",
    "supportWhatsappMessage": "support.whatsapp_message",
    "socialFacebook":              "social.facebook",
    "socialInstagram":             "social.instagram",
    "socialYoutube":               "social.youtube",
    "contributionUpiId":           "contribution.upi_id",
    "contributionBankName":        "contribution.bank_name",
    "contributionAccountName":     "contribution.account_name",
    "contributionAccountNumber":   "contribution.account_number",
    "contributionIfsc":            "contribution.ifsc",
    "contributionBankBranch":      "contribution.bank_branch",
    "platformRegistrationUpiId":   "platform.registration_upi_id",
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
