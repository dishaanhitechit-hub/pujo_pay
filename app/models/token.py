import enum
from ..extensions import db


class TokenTypeEnum(str, enum.Enum):
    single = "single"
    dual = "dual"
    bulk = "bulk"


class TokenStatusEnum(str, enum.Enum):
    active = "active"
    void = "void"


class Token(db.Model):
    __tablename__ = "tokens"

    id = db.Column(db.Integer, primary_key=True)
    token_no = db.Column(db.String(60), unique=True, nullable=False)
    token_serial = db.Column(db.Integer, nullable=False)
    type = db.Column(db.Enum(TokenTypeEnum), nullable=False)
    status = db.Column(
        db.Enum(TokenStatusEnum), nullable=False, default=TokenStatusEnum.active
    )
    participant_name = db.Column(db.String(120))
    topic = db.Column(db.String(200))
    org_name = db.Column(db.String(200), nullable=False)
    generated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    generated_at = db.Column(db.DateTime, server_default=db.func.now())
    batch_id = db.Column(db.String(36))

    generated_by = db.relationship("User", foreign_keys=[generated_by_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tokenNo": self.token_no,
            "slNo": self.token_serial,
            "type": self.type.value,
            "status": self.status.value,
            "participantName": self.participant_name,
            "topic": self.topic,
            "orgName": self.org_name,
            "generatedBy": {
                "id": self.generated_by_id,
                "name": self.generated_by.name if self.generated_by else None,
            },
            "generatedAt": self.generated_at.isoformat() if self.generated_at else None,
            "batchId": self.batch_id,
            "printUrl": f"/token/print/{self.token_no}",
            "viewUrl": f"/token/{self.token_no}",
        }
