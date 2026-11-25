"""Canonical game title and slug resolution helpers."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.models import Game

GAME_NAME_ALIASES = {
    '2048': '2048',
    '2048 cyber grid': '2048',
    'updown': '2048',
    'flappy bird': 'flappybird',
    'flappy birds': 'flappybird',
    'flappybird': 'flappybird',
    'mole': 'mole',
    'whack a mole': 'mole',
    'wake a mole': 'mole',
    'mole invasion: whack back!': 'mole',
    'moleeasy': 'mole',
    'molemedium': 'mole',
    'molehard': 'mole',
    'speedtype': 'speedtype',
    'speedtype pro': 'speedtype',
    'speedtypepro': 'speedtype',
    'maze': 'maze',
    'cyber labyrinth': 'maze',
    'mazeeasy': 'maze',
    'mazemedium': 'maze',
    'mazehard': 'maze',
    'mazeveasy': 'maze',
    'pong': 'pong',
    'vector pong classic': 'pong',
    'pong easy': 'pong',
    'pongeasy': 'pong',
    'pongmedium': 'pong',
    'ponghard': 'pong',
    'football': 'pong',
    'candy crush': 'candy-crush',
    'candy_crush': 'candy-crush',
    'cyber crush': 'candy-crush',
    'memorymatch': 'memorymatch',
    'memory match': 'memorymatch',
    'memory matrix': 'memorymatch',
    'memory match easy': 'memorymatch',
    'matchingeasy': 'memorymatch',
    'matchingmedium': 'memorymatch',
    'matchinghard': 'memorymatch',
    'matchinginsane': 'memorymatch',
    'tictactoe': 'tictactoe',
    'tic-tac-toe': 'tictactoe',
    'quantum tic-tac-toe': 'tictactoe',
    'towerblock': 'towerblock',
    'tower block': 'towerblock',
    'skyline tower block': 'towerblock',
    'crossword': 'crossword',
    'cross word': 'crossword',
    'neural crossword': 'crossword',
    'animal': 'crossword',
    'anime': 'crossword',
    'cities': 'crossword',
    'movie': 'crossword',
    'sport': 'crossword',
    'state': 'crossword',
    'quiz': 'quiz',
    'cyber quiz matrix': 'quiz',
    'trivia': 'quiz',
    'trivia madness': 'quiz',
    'aanimal': 'quiz',
    'cartoon': 'quiz',
    'food': 'quiz',
    'gk': 'quiz',
    'history': 'quiz',
    'indiansport': 'quiz',
    'movies': 'quiz',
    'place': 'quiz',
    'riddle': 'quiz',
    'stonepapersissors': 'stonepapersissors',
    'stone paper scissors': 'stonepapersissors',
    'rock paper scissors': 'stonepapersissors',
    'stonepapersissor': 'stonepapersissors',
    'tricky': 'tricky',
    'tricky brain quest': 'tricky',
    'trickygame': 'tricky',
    'relationship': 'relationship',
    'relations': 'relationship',
    'relationshipeasy': 'relationship',
    'relationshiphard': 'relationship',
    'blood relations mystery': 'relationship',
    'blood relations': 'relationship',
    'sequence': 'sequence',
    'mathsequence': 'sequence',
    'mathsequencegame': 'sequence',
    'sequence number logic': 'sequence',
    'neon cyber racer': 'neon-cyber-racer',
    'neon-cyber-racer': 'neon-cyber-racer',
    'neon-racer': 'neon-cyber-racer',
}


def resolve_game(game_name: str) -> Optional[Game]:
    """Resolve any game title, slug, or alias to its canonical Game model instance."""
    if not game_name or not game_name.strip():
        return None
    clean = game_name.strip()
    norm = clean.lower()

    matched = Game.query.filter((Game.title.ilike(clean)) | (Game.slug.ilike(clean))).first()
    if matched:
        return matched

    target_slug = GAME_NAME_ALIASES.get(norm)
    if not target_slug:
        for alias_key, alias_slug in GAME_NAME_ALIASES.items():
            if alias_key in norm or norm in alias_key:
                target_slug = alias_slug
                break

    if target_slug:
        return Game.query.filter_by(slug=target_slug).first()

    return None


def canonical_game_title(game_name: str) -> str:
    """Return canonical Game.title if known in catalog, otherwise stripped input."""
    if not game_name or not game_name.strip():
        return ""
    clean = game_name.strip()
    try:
        matched = resolve_game(clean)
        if matched and matched.title:
            return matched.title
    except Exception:
        pass
    return clean
