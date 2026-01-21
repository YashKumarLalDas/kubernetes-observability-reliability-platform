import os
import time
from fastapi import FastAPI, Response, status
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import redis

app = FastAPI(title="Observability Demo API")

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["path"]
)

def get_redis_client():
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, decode_responses=True)

@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    path = request.url.path
    REQUEST_LATENCY.labels(path=path).observe(duration)
    REQUEST_COUNT.labels(
        method=request.method,
        path=path,
        status_code=str(response.status_code)
    ).inc()

    return response

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    # readiness = dependency check (Redis)
    try:
        r = get_redis_client()
        r.ping()
        return {"status": "ready", "redis": "ok"}
    except Exception as e:
        return Response(
            content=f'{{"status":"not_ready","redis":"error","detail":"{str(e)}"}}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )

@app.get("/work")
def work(ms: int = 50):
    """
    Simulates CPU work to create load for HPA demo later.
    Increase ms to increase CPU usage.
    """
    end = time.time() + (ms / 1000.0)
    x = 0
    while time.time() < end:
        x += 1
    return {"status": "done", "ms": ms, "iterations": x}

@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
