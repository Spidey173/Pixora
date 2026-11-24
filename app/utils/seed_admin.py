"""Secure administrative account creation and seeding utility."""
import os
import sys
from typing import Optional

from app.database import db
from app.models import User


def seed_admin(
    username: Optional[str] = None,
    password: Optional[str] = None
) -> User:
    """Create or update the administrator account from environment variables.

    Reads ADMIN_USERNAME and ADMIN_PASSWORD. Refuses to run if ADMIN_PASSWORD is
    missing or shorter than 12 characters. Hashes the password using bcrypt.
    """
    admin_user = (username or os.environ.get("ADMIN_USERNAME", "admin")).strip()
    admin_pass = password if password is not None else os.environ.get("ADMIN_PASSWORD")

    if not admin_user:
        raise ValueError("ADMIN_USERNAME must not be empty.")

    if not admin_pass or len(admin_pass) < 12:
        raise ValueError("ADMIN_PASSWORD is required and must be at least 12 characters long.")

    user = User.query.filter_by(username=admin_user).first()
    if not user:
        user = User(
            username=admin_user,
            is_admin=True,
            is_guest=False
        )
        db.session.add(user)
    else:
        user.is_admin = True
        user.is_guest = False

    user.set_password(admin_pass)
    db.session.commit()
    return user


def main():
    """CLI entrypoint for seeding the administrator account."""
    from app import create_app

    app = create_app()
    with app.app_context():
        try:
            user = seed_admin()
            print(f"Admin user '{user.username}' successfully created/updated.")
        except ValueError as err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

