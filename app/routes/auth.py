"""Authentication routes for login, registration, and logout."""
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app.extensions import db, limiter
from app.forms import LoginForm, RegisterForm
from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def login():
    """Handle user authentication, guest access, and session creation."""
    if current_user.is_authenticated:
        return redirect(url_for('main.games'))

    form = LoginForm()
    if form.validate_on_submit():
        raw_username = form.username.data.strip()
        password = form.password.data.strip() if form.password.data else None
        remember = form.remember_me.data

        user = User.query.filter_by(username=raw_username).first()

        if user:
            # User exists
            if user.password_hash:
                # Password-protected account
                if not password:
                    flash('This account is protected with a password. Please enter your passcode.', 'warning')
                    return render_template('Games/login.html', form=form)
                elif not user.check_password(password):
                    flash('Invalid passcode for this codename. Access denied.', 'danger')
                    return render_template('Games/login.html', form=form)
            
            # Update last seen timestamp
            user.last_seen = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=remember)
            
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.games')
            return redirect(next_page)
        else:
            # New user registration on the fly (guest or password account)
            new_user = User(
                username=raw_username,
                is_guest=(password is None),
                created_at=datetime.now(timezone.utc),
                last_seen=datetime.now(timezone.utc)
            )
            if password:
                new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=remember)
            
            flash(f'Welcome to the arcade, {raw_username}!', 'success')
            return redirect(url_for('main.games'))

    return render_template('Games/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def register():
    """Register a new protected account with password."""
    if current_user.is_authenticated:
        return redirect(url_for('main.games'))

    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data.strip()

        user = User.query.filter_by(username=username).first()
        if user and not user.password_hash:
            # Upgrade existing guest account to password protected
            user.set_password(password)
            user.is_guest = False
            user.last_seen = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user)
            flash('Account successfully secured with passcode!', 'success')
            return redirect(url_for('main.games'))

        new_user = User(
            username=username,
            is_guest=False,
            created_at=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc)
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash('Registration complete! Welcome to Pixora.', 'success')
        return redirect(url_for('main.games'))

    return render_template('Games/login.html', form=form, register_mode=True)


@auth_bp.route('/logout')
def logout():
    """Clear session and log out the user."""
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for('auth.login'))
