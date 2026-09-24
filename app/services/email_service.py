import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _smtp_config() -> dict:
    return {
        "server":   os.getenv("MAIL_SERVER", "smtp.gmail.com"),
        "port":     int(os.getenv("MAIL_PORT", 587)),
        "use_tls":  os.getenv("MAIL_USE_TLS", "true").lower() == "true",
        "username": os.getenv("MAIL_USERNAME", ""),
        "password": os.getenv("MAIL_PASSWORD", ""),
        "from_email": os.getenv("MAIL_FROM_EMAIL", os.getenv("MAIL_USERNAME", "")),
        "from_name":  os.getenv("MAIL_FROM_NAME", "PujoPay Platform"),
    }


def send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Send an email. Returns True on success, False on failure."""
    cfg = _smtp_config()
    if not cfg["username"] or not cfg["password"]:
        logger.warning("Email not configured — skipping send to %s", to_email)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{cfg['from_name']} <{cfg['from_email']}>"
    msg["To"]      = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(cfg["server"], cfg["port"], timeout=10) as smtp:
            if cfg["use_tls"]:
                smtp.starttls()
            smtp.login(cfg["username"], cfg["password"])
            smtp.sendmail(cfg["from_email"], to_email, msg.as_string())
        logger.info("Email sent to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return False


def send_org_credentials_email(
    to_email: str,
    contact_name: str,
    org_name: str,
    admin_email: str,
    temp_password: str,
    otp_code: str,
) -> bool:
    subject = f"Welcome to PujoPay — Your {org_name} Credentials"

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;">
      <h2 style="color:#4f46e5;">Welcome to PujoPay!</h2>
      <p>Hi <strong>{contact_name}</strong>,</p>
      <p>Your organisation <strong>{org_name}</strong> has been successfully registered on PujoPay.
         Below are your login credentials.</p>

      <table style="background:#f9f9f9;border-radius:8px;padding:16px;width:100%;border-collapse:collapse;">
        <tr>
          <td style="padding:8px 12px;font-weight:bold;">Admin Email (Login ID)</td>
          <td style="padding:8px 12px;">{admin_email}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;font-weight:bold;">Temporary Password</td>
          <td style="padding:8px 12px;">{temp_password}</td>
        </tr>
        <tr style="background:#fff3cd;">
          <td style="padding:8px 12px;font-weight:bold;">One-Time Setup Code</td>
          <td style="padding:8px 12px;font-size:22px;letter-spacing:4px;font-weight:bold;color:#d97706;">
            {otp_code}
          </td>
        </tr>
      </table>

      <p style="margin-top:20px;">
        Use the <strong>One-Time Setup Code</strong> along with your credentials on your first login
        to activate your account and set a new password.
      </p>
      <p style="color:#e53e3e;font-size:13px;">
        This code can only be used once. Please change your password immediately after first login.
      </p>
      <hr style="margin:24px 0;border:none;border-top:1px solid #eee;">
      <p style="font-size:12px;color:#999;">
        If you did not request this, please contact support immediately.
      </p>
    </body></html>
    """

    text_body = (
        f"Welcome to PujoPay!\n\n"
        f"Organisation: {org_name}\n"
        f"Admin Email: {admin_email}\n"
        f"Temporary Password: {temp_password}\n"
        f"One-Time Setup Code: {otp_code}\n\n"
        f"Use the setup code on your first login to activate your account."
    )

    return send_email(to_email, subject, html_body, text_body)
