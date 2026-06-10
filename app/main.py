from fastapi import FastAPI

app = FastAPI(title="Label Verifier")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
