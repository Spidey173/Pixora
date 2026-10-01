"""WTForms form classes for authentication and input validation."""
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

from app.models import User


class LoginForm(FlaskForm):
    """Player login form supporting password verification or guest fallback."""
    username = StringField(
        'Player Codename',
        validators=[
            DataRequired(message="Codename is required."),
            Length(min=2, max=30, message="Codename must be between 2 and 30 characters.")
        ]
    )
    password = PasswordField(
        'Passcode (Optional for Guest)',
        validators=[Optional(), Length(min=4, max=100)]
    )
    remember_me = BooleanField('Keep Link Active')
    submit = SubmitField('ACTIVATE GAMING')


class AdminLoginForm(FlaskForm):
    """Dedicated secure login form for Admin Console access."""
    username = StringField(
        'Admin Username',
        validators=[DataRequired(message="Admin username is required.")]
    )
    password = PasswordField(
        'Master Password',
        validators=[DataRequired(message="Admin password is required.")]
    )
    submit = SubmitField('ACCESS ADMIN CONSOLE')


class RegisterForm(FlaskForm):
    """Player registration form for protected accounts."""
    username = StringField(
        'Player Codename',
        validators=[
            DataRequired(message="Codename is required."),
            Length(min=2, max=30, message="Codename must be between 2 and 30 characters.")
        ]
    )
    password = PasswordField(
        'Security Passcode',
        validators=[
            DataRequired(message="Password is required."),
            Length(min=6, max=100, message="Password must be at least 6 characters.")
        ]
    )
    confirm_password = PasswordField(
        'Confirm Passcode',
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo('password', message="Passcodes must match.")
        ]
    )
    submit = SubmitField('REGISTER ACCOUNT')

    def validate_username(self, field):
        """Ensure username contains valid characters and is unique."""
        cleaned = field.data.strip()
        if not cleaned.replace('_', '').replace('-', '').isalnum():
            raise ValidationError('Codename can only contain letters, numbers, hyphens, and underscores.')
        user = User.query.filter_by(username=cleaned).first()
        if user and user.password_hash is not None:
            raise ValidationError('This codename is already registered with a password. Please log in.')


class GameUploadForm(FlaskForm):
    """Admin form for uploading game zip packages to Cloudflare R2 or registering custom web games."""
    title = StringField('Game Title', validators=[
        DataRequired(message="Title is required."),
        Length(min=2, max=120)
    ])
    slug = StringField('URL Slug (e.g. cyber-runner)', validators=[
        DataRequired(message="Slug is required."),
        Length(min=2, max=80)
    ])
    category = StringField('Category (e.g. Arcade, Action, Puzzle, Sci-Fi)', validators=[
        DataRequired(message="Category is required."),
        Length(min=2, max=50)
    ])
    play_url = StringField('Direct Web Game URL (Optional if uploading .zip)', validators=[
        Optional(),
        Length(max=500)
    ])
    description = StringField('Description', validators=[
        Optional(),
        Length(max=500)
    ])
    controls_guide = StringField('Controls Guide (e.g. Arrow keys to steer)', validators=[
        Optional(),
        Length(max=300)
    ])
    submit = SubmitField('DEPLOY GAME TO PLATFORM')

