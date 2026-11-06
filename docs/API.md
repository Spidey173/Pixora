# 👾 Pixora REST Telemetry & Leaderboard API Specification

Welcome to the **Pixora REST API Documentation**. This document describes all available endpoints for session telemetry, gameplay history tracking, high score submission, leaderboards, and system health checks.

---

## 🔐 Base Headers & Authentication

For endpoints requiring authentication, requests must be accompanied by an active session cookie established via `/login`.

Common JSON Response Content-Type: `application/json`

---

## 📡 Endpoints Summary

| Endpoint | Method | Auth Required | Description |
|---|---|---|---|
| `/start_game/<game_name>` | POST | Yes | Logs the launch of a new mini-game session |
| `/end_game/<game_name>` | POST | Yes | Logs game completion and calculates duration |
| `/api/history` | GET | Yes | Returns real-time session logs for the authenticated player |
| `/api/score/submit` | POST | Yes | Submits a high score for a specific mini-game |
| `/api/leaderboard/<game_name>` | GET | No | Returns the top 10 scores for a given game |
| `/api/health` | GET | No | System telemetry and database status check |

---

## 🛠️ Endpoint Specifications

### 1. Start Game Session
`POST /start_game/<game_name>`

#### Response (200 OK)
```json
{
  "status": "logged",
  "game": "2048",
  "session_id": 42
}
```

---

### 2. End Game Session
`POST /end_game/<game_name>`

#### Response (200 OK)
```json
{
  "status": "ended",
  "game": "2048"
}
```

---

### 3. Retrieve Player History
`GET /api/history`

#### Response (200 OK)
```json
{
  "username": "CyberTester",
  "count": 2,
  "history": [
    {
      "id": 12,
      "player_id": 1,
      "game_name": "2048",
      "timestamp": "2026-09-05 01:40:00",
      "duration_seconds": 120
    }
  ]
}
```

---

### 4. Submit High Score
`POST /api/score/submit`

#### Request Payload
```json
{
  "game_name": "2048",
  "score": 3200
}
```

#### Response (201 Created)
```json
{
  "status": "success",
  "message": "Score recorded",
  "score": {
    "id": 1,
    "player_id": 1,
    "username": "CyberTester",
    "game_name": "2048",
    "score": 3200,
    "achieved_at": "2026-09-05T01:40:00.000Z"
  }
}
```

---

### 5. Get Game Leaderboard
`GET /api/leaderboard/<game_name>`

#### Response (200 OK)
```json
{
  "game_name": "2048",
  "leaderboard": [
    {
      "id": 1,
      "username": "CyberTester",
      "score": 3200,
      "achieved_at": "2026-09-05T01:40:00.000Z"
    }
  ]
}
```

---

### 6. System Health Check
`GET /api/health`

#### Response (200 OK)
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-09-05T01:40:00.000Z",
  "version": "1.2.0"
}
```
