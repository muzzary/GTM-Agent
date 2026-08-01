import os

from fastapi import FastAPI

from src.runtime.settings import Settings

settings = Settings.from_mapping(os.environ)
app = FastAPI(title="GTM Agent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "gtm-agent", "status": "ok"}
