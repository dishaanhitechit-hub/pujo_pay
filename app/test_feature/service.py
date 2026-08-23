import io
import uuid
from datetime import date

import qrcode
import qrcode.constants

from ..extensions import db
from .models import AttendanceSession, AttendanceRecord


# ── Session management ──────────────────────────────────────────────────────

def get_or_create_today_session() -> AttendanceSession:
    today = date.today()
    session = AttendanceSession.query.filter_by(date=today, is_active=True).first()
    if not session:
        last = (
            AttendanceSession.query
            .filter_by(date=today)
            .order_by(AttendanceSession.session_number.desc())
            .first()
        )
        session_number = (last.session_number + 1) if last else 1
        session = AttendanceSession(
            date=today,
            session_number=session_number,
            qr_token=uuid.uuid4().hex,
            is_active=True,
        )
        db.session.add(session)
        db.session.commit()
    return session


def reset_session() -> AttendanceSession:
    today = date.today()
    AttendanceSession.query.filter_by(date=today, is_active=True).update({"is_active": False})
    db.session.commit()
    return get_or_create_today_session()


def get_session_by_token(token: str) -> AttendanceSession | None:
    return AttendanceSession.query.filter_by(qr_token=token, is_active=True).first()


def get_today_sessions() -> list[AttendanceSession]:
    return (
        AttendanceSession.query
        .filter_by(date=date.today())
        .order_by(AttendanceSession.session_number.asc())
        .all()
    )


# ── Attendance submission ───────────────────────────────────────────────────

def submit_attendance(
    session: AttendanceSession,
    name: str,
    phone: str,
    address: str | None,
    device_fp: str | None,
    ip: str | None,
) -> tuple[AttendanceRecord | None, str | None]:
    if AttendanceRecord.query.filter_by(session_id=session.id, phone=phone).first():
        return None, "phone"

    if device_fp and AttendanceRecord.query.filter_by(session_id=session.id, device_fingerprint=device_fp).first():
        return None, "device"

    record = AttendanceRecord(
        session_id=session.id,
        name=name.strip(),
        phone=phone.strip(),
        address=address.strip() if address else None,
        device_fingerprint=device_fp,
        ip_address=ip,
    )
    db.session.add(record)
    db.session.commit()
    return record, None


# ── QR generation ──────────────────────────────────────────────────────────

def generate_qr_png(url: str) -> bytes:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Records ────────────────────────────────────────────────────────────────

def get_today_records() -> list[dict]:
    today = date.today()
    sessions = AttendanceSession.query.filter_by(date=today).all()
    if not sessions:
        return []
    session_map = {s.id: s.session_number for s in sessions}
    records = (
        AttendanceRecord.query
        .filter(AttendanceRecord.session_id.in_(list(session_map.keys())))
        .order_by(AttendanceRecord.created_at.desc())
        .all()
    )
    result = []
    for r in records:
        d = r.to_dict()
        d["sessionNumber"] = session_map.get(r.session_id, "?")
        result.append(d)
    return result
