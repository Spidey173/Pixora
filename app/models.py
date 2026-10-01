"""SQLAlchemy database models for Pixora."""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return db.session.get(User, int(user_id))


class User(UserMixin, db.Model):
    """User account model for authentication and history tracking."""
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True)
    is_guest = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    sessions = db.relationship(
        'GameplaySession',
        backref='player',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='GameplaySession.started_at.desc()'
    )
    scores = db.relationship(
        'GameScore',
        backref='player',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='GameScore.score.desc()'
    )

    def set_password(self, password: str):
        """Hash and set the user's password."""
        if password:
            self.password_hash = generate_password_hash(password)
        else:
            self.password_hash = None

    def check_password(self, password: str) -> bool:
        """Verify the user's password."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def total_plays(self) -> int:
        """Return total games played count."""
        return self.sessions.count()

    @property
    def highest_score(self) -> int:
        """Return highest score across all games."""
        top_score = self.scores.order_by(GameScore.score.desc()).first()
        return top_score.score if top_score else 0

    def to_dict(self):
        """Serialize user to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'is_guest': self.is_guest,
            'is_admin': self.is_admin,
            'total_plays': self.total_plays,
            'highest_score': self.highest_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }

    def __repr__(self):
        return f"<User id={self.id} username='{self.username}'>"


class GameplaySession(db.Model):
    """Gameplay activity logging model."""
    __tablename__ = 'gameplay'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id', ondelete='CASCADE'), nullable=False, index=True)
    game_name = db.Column(db.String(100), nullable=False, index=True)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)

    @property
    def formatted_timestamp(self) -> str:
        """Format timestamp as standard YYYY-MM-DD HH:MM:SS string."""
        if self.started_at:
            return self.started_at.strftime('%Y-%m-%d %H:%M:%S')
        return ""

    def to_dict(self):
        """Serialize gameplay session to dictionary."""
        return {
            'id': self.id,
            'player_id': self.player_id,
            'username': self.player.username if self.player else None,
            'game_name': self.game_name,
            'timestamp': self.formatted_timestamp,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'duration_seconds': self.duration_seconds
        }

    def __repr__(self):
        return f"<GameplaySession id={self.id} player_id={self.player_id} game='{self.game_name}'>"


class GameScore(db.Model):
    """High score tracking model per game per player."""
    __tablename__ = 'game_scores'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id', ondelete='CASCADE'), nullable=False, index=True)
    game_name = db.Column(db.String(100), nullable=False, index=True)
    score = db.Column(db.Integer, nullable=False, default=0, index=True)
    achieved_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def to_dict(self):
        """Serialize score to dictionary."""
        return {
            'id': self.id,
            'player_id': self.player_id,
            'username': self.player.username if self.player else 'Guest',
            'game_name': self.game_name,
            'score': self.score,
            'achieved_at': self.achieved_at.isoformat() if self.achieved_at else None
        }

    def __repr__(self):
        return f"<GameScore id={self.id} player_id={self.player_id} game='{self.game_name}' score={self.score}>"


class Game(db.Model):
    """Dynamic game catalog model supporting Cloudflare R2 CDN assets."""
    __tablename__ = 'games'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), default='Arcade', nullable=False, index=True)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    # If game assets are hosted on Cloudflare R2:
    r2_asset_key = db.Column(db.String(255), nullable=True)
    # The direct playable URL (either Cloudflare R2 public URL or relative local path):
    play_url = db.Column(db.String(500), nullable=False)
    controls_guide = db.Column(db.Text, nullable=True)
    play_count = db.Column(db.Integer, default=0, nullable=False)
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        """Serialize game to dictionary."""
        return {
            'id': self.id,
            'slug': self.slug,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'thumbnail_url': self.thumbnail_url,
            'play_url': self.play_url,
            'controls_guide': self.controls_guide,
            'play_count': self.play_count,
            'is_featured': self.is_featured,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<Game id={self.id} slug='{self.slug}' title='{self.title}'>"

