from ...models.user import User


def get_user_by_credentials(email: str, password: str) -> User | None:
    user = User.query.filter_by(email=email.strip().lower(), is_active=True).first()
    if user and user.check_password(password):
        return user
    return None


def get_active_user(user_id: int) -> User | None:
    return User.query.filter_by(id=user_id, is_active=True).first()
