import enum
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db


class RoleEnum(str, enum.Enum):
    admin = "admin"
    executive = "executive"
    committee = "committee"
    general = "general"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(20))
    upi_id = db.Column(db.String(100))
    whatsapp_no = db.Column(db.String(20))
    role = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.general)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "upiId": self.upi_id,
            "whatsappNo": self.whatsapp_no,
            "role": self.role.value,
            "isActive": self.is_active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
