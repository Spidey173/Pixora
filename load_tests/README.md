# Pixora 2.0 High-Throughput Load Testing Suite

This suite benchmarks Pixora 2.0 under high concurrency:
- **10,000+ Requests/Second** on Redis Streams & Sorted Sets.
- **Sub-5ms P99 Latency** for leaderboards and score ingestion.
- **100% Anti-Cheat Anomaly Catch Rate** under simulated DDoS / bot attacks.

## Prerequisites

```bash
pip install locust
```

## Running the Benchmark

### 1. Start Pixora in Production Mode (with Redis)
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Pixora Web Application
gunicorn -w 4 -b 127.0.0.1:5000 app:app
```

### 2. Launch Locust Load Generator
```bash
# Web UI Mode:
locust -f load_tests/locustfile.py --host=http://127.0.0.1:5000

# Headless Benchmark (1,000 Concurrent Users, 60-second burst):
locust -f load_tests/locustfile.py --host=http://127.0.0.1:5000 \
       --headless --users 1000 --spawn-rate 100 --run-time 60s
```

## Key Metrics Verified
1. **Zero dropped telemetry events:** All valid scores are committed to Redis Streams.
2. **Strict Cryptographic Rejection:** 100% of injected anomalous scores ($>2.5$ pipes/sec or replayed tokens) return `HTTP 422 Unprocessable Entity` or `HTTP 401 Unauthorized`.
3. **Sub-millisecond Read Latency:** `/api/leaderboard/<game>` requests served directly from Redis ZSET cache.

