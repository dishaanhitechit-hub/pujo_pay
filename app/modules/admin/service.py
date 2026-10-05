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
    # Member ID format
    "memberIdPrefix":              "Prefix for auto-generated member IDs (e.g. ABC)",
    "memberIdDigits":              "Number of digits in the member ID sequence (3-6, default 4)",
    # Club identity (public website)
    "clubNameVernacular":   "Club name in local language (e.g. শতদল)",
    "clubNameEn":           "Club name in English (e.g. Shatadal)",
    "clubTagline":          "Short location/tagline (e.g. Kolaghat)",
    "clubDescription":      "One-line club description shown on the public site",
    "clubCity":             "City / town (e.g. Kolaghat)",
    "clubState":            "State (e.g. West Bengal)",
    "clubFoundingYear":     "Year the club was founded (e.g. 1975)",
    "clubLogoUrl":          "URL of the club logo image",
    "clubHeroImageUrl":     "URL of the hero / banner image on the public home page",
    "clubAboutText":        "Full about-us paragraph shown on the About page",
    "clubSiteUrl":          "Canonical public website URL (used for OG tags)",
    "clubMetaDescription":  "SEO meta description for the public site",
    "clubOgImageUrl":       "Open Graph image URL for the public site",
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
    "memberIdPrefix":              "member_id.prefix",
    "memberIdDigits":              "member_id.digits",
    # Club identity
    "clubNameVernacular":   "club.name_vernacular",
    "clubNameEn":           "club.name_en",
    "clubTagline":          "club.tagline",
    "clubDescription":      "club.description",
    "clubCity":             "club.city",
    "clubState":            "club.state",
    "clubFoundingYear":     "club.founding_year",
    "clubLogoUrl":          "club.logo_url",
    "clubHeroImageUrl":     "club.hero_image_url",
    "clubAboutText":        "club.about_text",
    "clubSiteUrl":          "club.site_url",
    "clubMetaDescription":  "club.meta_description",
    "clubOgImageUrl":       "club.og_image_url",
}


def get_all(org_id: int | None = None) -> dict:
    rows = AppConfig.query.filter_by(org_id=org_id).all()
    return {row.key: row.value for row in rows}


def set_keys(payload: dict, org_id: int | None = None) -> tuple[dict, dict]:
    """Set one or more config keys. Returns (updated, errors)."""
    updated, errors = {}, {}
    for key, value in payload.items():
        if key not in ALLOWED_KEYS:
            errors[key] = f"unknown key — allowed: {list(ALLOWED_KEYS)}"
            continue
        db_key = _KEY_MAP[key]
        AppConfig.set(db_key, str(value).strip(), org_id=org_id)
        updated[key] = str(value).strip()
    return updated, errors
