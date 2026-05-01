"""FastAPI wrapper for stealth-runner (SOTA #14)."""
from fastapi import FastAPI
from pydantic import BaseModel, Field
from runner.state_machine import SurveyRunner
import anyio

app = FastAPI(title="stealth-runner API", version="0.1.0")

class SurveyRequest(BaseModel):
    url: str = Field(..., description="Survey URL")
    max_steps: int = Field(default=50, ge=1, le=200)

@app.get("/health")
async def health():
    try:
        import subprocess; subprocess.run(["playstealth", "--version"], capture_output=True, timeout=5)
        return {"status": "ok", "deps": "all_available"}
    except: return {"status": "degraded"}

@app.get("/balance")
async def balance():
    log = Path.home() / ".stealth_runner" / "traces.jsonl"
    lines = log.read_text().strip().split("\n") if log.exists() else []
    eur = 0.0
    for line in lines[-5:]:
        try: eur = max(eur, float(json.loads(line).get("context",{}).get("earnings_eur", 0)))
        except: pass
    return {"earnings_eur": eur, "scans": len(lines)}

if __name__ == "__main__":
    import uvicorn; uvicorn.run(app, host="127.0.0.1", port=8420)
