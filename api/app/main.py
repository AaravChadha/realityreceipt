from fastapi import FastAPI

app = FastAPI(title="RealityReceipt API")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
