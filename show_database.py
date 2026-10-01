"""Pixora Database Inspector Utility.

For the interactive web admin console, run `python app.py` and navigate to `/admin`.
"""
import argparse

from app import create_app
from app.models import GameplaySession, GameScore, User


def inspect_database(show_scores=True, show_players=True):
    """Inspect and display summary of database players, scores, and logs."""
    app = create_app('development')
    with app.app_context():
        players = User.query.order_by(User.created_at.desc()).all()
        total_sessions = GameplaySession.query.count()
        total_scores = GameScore.query.count()

        print("\n" + "=" * 60)
        print("👾 PIXORA DATABASE TELEMETRY & HIGH SCORES")
        print("=" * 60)
        print(f"Total Players: {len(players)}")
        print(f"Total Gameplay Sessions: {total_sessions}")
        print(f"Total Scores Recorded: {total_scores}\n")

        if show_players and players:
            print("--- REGISTERED PLAYERS ---")
            for player in players:
                status = "🔒 Secured" if player.password_hash else "👤 Guest"
                print(f" • {player.username:<20} | {player.total_plays} plays | High Score: {player.highest_score:<6} | {status}")
            print()

        if show_scores:
            top_scores = GameScore.query.order_by(GameScore.score.desc()).limit(10).all()
            if top_scores:
                print("--- TOP HIGH SCORES ---")
                for s in top_scores:
                    uname = s.player.username if s.player else "Guest"
                    print(f" • {s.game_name:<20} | Score: {s.score:<8} | Player: {uname}")
                print()

        print("=" * 60)
        print("Web Admin Portal is available at: http://localhost:5000/admin\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Pixora Database Inspector CLI")
    parser.add_argument('--no-scores', action='store_true', help="Hide high score breakdown")
    parser.add_argument('--no-players', action='store_true', help="Hide player list")
    args = parser.parse_args()

    inspect_database(show_scores=not args.no_scores, show_players=not args.no_players)