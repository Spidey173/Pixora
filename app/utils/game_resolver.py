"""Canonical game title, slug resolution, and normalized leaderboard ranking helpers."""
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


@dataclass
class NormalizedLeaderboardEntry:
    """Leaderboard row enriched with per-game world record normalization."""
    player_id: int
    player: Any
    game_name: str
    score: int
    achieved_at: Optional[datetime]
    world_record: int
    normalized_pct: float
    total_normalized_pct: float
    games_played: int


def build_normalized_all_titles_leaderboard(scores: list, limit: int = 30) -> list[NormalizedLeaderboardEntry]:
    """Rank players across different games using normalized scores (score / game world record * 100).

    Each game's world record equals 100.0% so high-magnitude games (e.g. Synthwave Pinball)
    do not drown out low-magnitude games (e.g. Flappy Birds or 2048).
    """
    if not scores:
        return []

    # 1. Determine world record and best score per (player_id, canonical_game)
    wr_by_game: dict[str, int] = {}
    best_per_player_game: dict[tuple[int, str], Any] = {}

    for s in scores:
        canon_game = canonical_game_title(s.game_name) or s.game_name
        val = int(s.score or 0)
        if val > wr_by_game.get(canon_game, 0):
            wr_by_game[canon_game] = val

        key = (s.player_id, canon_game)
        prev = best_per_player_game.get(key)
        if prev is None or val > int(prev.score or 0):
            best_per_player_game[key] = s

    # 2. Aggregate per player across games
    player_entries: dict[int, list[tuple[Any, str, float, int]]] = {}
    for (pid, canon_game), score_obj in best_per_player_game.items():
        wr = wr_by_game.get(canon_game, 0)
        pct = round((int(score_obj.score or 0) / wr) * 100.0, 1) if wr > 0 else 0.0
        player_entries.setdefault(pid, []).append((score_obj, canon_game, pct, wr))

    ranked_rows: list[NormalizedLeaderboardEntry] = []
    for pid, entries in player_entries.items():
        # Pick player's top normalized achievement (tie-break by raw score)
        entries.sort(key=lambda item: (item[2], int(item[0].score or 0)), reverse=True)
        best_obj, best_game, best_pct, best_wr = entries[0]
        total_pct = round(sum(item[2] for item in entries), 1)
        ranked_rows.append(
            NormalizedLeaderboardEntry(
                player_id=pid,
                player=best_obj.player,
                game_name=best_game,
                score=int(best_obj.score or 0),
                achieved_at=best_obj.achieved_at,
                world_record=best_wr,
                normalized_pct=best_pct,
                total_normalized_pct=total_pct,
                games_played=len(entries),
            )
        )

    ranked_rows.sort(
        key=lambda row: (
            -row.normalized_pct,
            -row.total_normalized_pct,
            -row.games_played,
            -row.score,
            row.achieved_at.timestamp() if row.achieved_at else float("inf"),
        )
    )
    return ranked_rows[:limit]
