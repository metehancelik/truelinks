from fastapi import FastAPI

app = FastAPI(title="Lease and property-issue agents")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the container platform."""
    return {"status": "ok"}
