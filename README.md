# 👾 Pixora — Retro Arcade Gaming Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000.svg?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-ff007f.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

A full-stack arcade gaming platform built with **Flask** and a **cyberpunk UI**. Features 17 playable mini-games, player authentication, real-time leaderboards powered by Redis, and an admin dashboard.

---

## 🎮 Features

- **17 Playable Mini-Games** across Puzzle, Arcade, Brain, and Strategy categories
- **Live Leaderboards** — Redis sorted sets for instant score ranking with SQLite/Postgres persistence
- **Universal Score Bridge** — auto-detects game completion and submits scores from every game
- **Player Authentication** — secure login/register with hashed passwords and guest access
- **Gameplay Telemetry** — session tracking, play counts, and duration logging via async event queue
- **Hall of Fame** — per-game and global championship leaderboards with podium rankings
- **Admin Dashboard** — player management, telemetry metrics, and game catalog controls
- **Cyberpunk Aesthetic** — neon gradients, glassmorphism, CRT scanlines, and particle effects

## 🕹️ Game Catalog

| Category | Games |
|----------|-------|
| **Puzzle** | 2048, Candy Crush, Maze, Crossword, Sequence, Tricky |
| **Arcade** | Flappy Bird, Whack-a-Mole, Tower Block, Stone Paper Scissors, Neon Cyber Racer |
| **Brain** | Memory Match, Quiz, Blood Relations |
| **Strategy** | Pong, Tic-Tac-Toe |
| **Skill** | SpeedType Pro |

---

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.11+, Flask (App Factory), SQLAlchemy ORM |
| **Database** | SQLite (dev) / PostgreSQL (prod), Redis (leaderboards & event queue) |
| **Auth & Security** | Flask-Login, Flask-WTF (CSRF), Flask-Limiter, Bcrypt |
| **Frontend** | HTML5, CSS3, JavaScript, HTML5 Canvas |
| **Storage** | Cloudflare R2 (game asset CDN) |
| **Testing** | Pytest, Ruff, GitHub Actions CI |

---

## 🚀 Getting Started

```bash
# Clone
git clone https://github.com/Spidey173/Pixora.git
cd Pixora

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Start the server
python app.py
```

Open [http://localhost:5000](http://localhost:5000) to enter the arcade.

---

## 📂 Project Structure

```
Pixora/
├── app/
│   ├── __init__.py          # App Factory & middleware
│   ├── config.py            # Environment configs (Dev/Test/Prod)
│   ├── models.py            # User, GameplaySession, GameScore, Game
│   ├── routes/
│   │   ├── auth.py          # Login, register, logout
│   │   ├── main.py          # Hub, leaderboards, score & telemetry APIs
│   │   ├── games.py         # Game route registry (17 games)
│   │   └── admin.py         # Admin dashboard
│   └── utils/
│       ├── telemetry_queue.py  # Redis/in-memory async event queue
│       ├── seed_games.py       # Game catalog seeder
│       └── reset_and_seed.py   # Full DB reset & sample data
├── templates/
│   ├── player.html          # Universal game player with score bridge
│   └── Games/               # 17 game templates + arcade hub
├── static/                  # CSS, images, game assets, audio
├── tests/                   # Pytest suite
├── app.py                   # Entry point
└── requirements.txt
```

---

## 🎯 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/games` | GET | Arcade hub with game catalog |
| `/play/<slug>` | GET | Launch game in player shell |
| `/api/score/submit` | POST | Submit game score |
| `/api/leaderboard/<game>` | GET | Top 10 + personal best + world record |
| `/api/history` | GET | Player session history |
| `/api/health` | GET | System health & telemetry metrics |
| `/start_game/<name>` | POST | Log session start |
| `/end_game/<name>` | POST | Log session end & duration |
| `/admin` | GET | Admin dashboard |

---

## 🧪 Testing

```bash
pytest -v          # Run test suite
ruff check .       # Lint check
python show_database.py   # Inspect DB records
```

---

## 👤 Developer

**Pruthvi R** — [@Spidey173](https://github.com/Spidey173) · [LinkedIn](https://www.linkedin.com/in/pruthvi-r-48ba9b2b4/)

## 📝 License

MIT License — free to use and adapt. 🕹️
