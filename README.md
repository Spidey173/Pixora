# Pixora Arcade

A retro web arcade with 17+ playable mini-games, user accounts, and fast browser gameplay.

## What's Inside

- **17+ Mini-Games**: 2048, Flappy Bird, Neon Cyber Racer, SpeedType Pro, Tic-Tac-Toe, Pong, Memory Match, and more.
- **User Accounts**: Sign up, log in, and track your played games.
- **Fast Loading**: Optimized WebP thumbnails, eager above-the-fold loading, and long-lived browser caching.
- **Admin Panel**: Manage games and users at `/admin`.

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy (SQLite locally, PostgreSQL in production)
- **Frontend**: Jinja2 templates + Next.js
- **Tests**: `pytest`

## Quick Start (Local)

1. **Clone the repo**
   ```bash
   git clone https://github.com/Spidey173/Pixora17.git
   cd Pixora17
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**
   ```bash
   ./run.sh
   ```
   Open `http://127.0.0.1:8000` in your browser.

## Running Tests

```bash
pytest -q
```

## Live Demo

https://pixora18.vercel.app/
