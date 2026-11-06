# Pixora - Arcade Gaming Platform

Pixora is a retro-style web arcade platform with 17 mini-games, user accounts, and real-time leaderboards.

---

## Features

- **17 Mini-Games**: Includes classics like 2048, Flappy Bird, Speed Typing, Pong, Memory Match, Whack-a-Mole, Tic-Tac-Toe, and more.
- **User Accounts & Guest Mode**: Players can register an account to save their scores or play immediately as a guest.
- **Live Leaderboards**: Tracks top scores for each game.
- **Real-Time Player Counter**: Uses WebSockets to show how many players are currently in each game.
- **Basic Score Validation**: Checks game duration and score rate to prevent impossible scores.
- **Admin Dashboard**: Simple admin view to see player stats, registered games, and recorded scores.

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Database**: SQLite (default for easy setup) / PostgreSQL with SQLAlchemy
- **Caching & Real-Time**: Redis (for live player presence and fast score queues)
- **Frontend**: HTML5, CSS3, JavaScript (rendered with Jinja2 templates)
- **Testing**: Pytest

---

## Getting Started

### 1. Prerequisites
- Python 3.11 or higher
- Redis (optional, in-memory fallback is used if Redis is not running)

### 2. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the App
```bash
python app.py
```
Or:
```bash
./run.sh
```

Now open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Optional: Running with Docker

If you prefer to run everything using Docker:
```bash
docker compose up --build
```
This starts PostgreSQL, Redis, and the Pixora app together.

---

## Project Structure

```
Pixora/
├── app/
│   ├── models.py         # Database models (User, Game, GameScore)
│   ├── database.py       # SQLAlchemy database connection
│   ├── templates.py      # Jinja2 template setup
│   ├── auth_deps.py      # Session and user helpers
│   ├── routers/          # Route handlers (auth, hub, games, admin)
│   ├── utils/            # Helper utilities and game catalog seed data
│   └── services/         # Anti-cheat validation logic
├── public/
│   └── games/            # Standalone game assets and bundles
├── static/               # CSS, JavaScript, and image files
├── templates/            # HTML templates
├── tests/                # Unit and integration tests
├── gateway.py            # Main FastAPI application and WebSocket endpoints
├── worker.py             # Background worker for score processing
├── app.py                # Main entrypoint to start the server
└── requirements.txt      # Python dependencies
```

---

## Running Tests

To run the automated tests:
```bash
pytest
```

---

## License

MIT License.
