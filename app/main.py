"""FastAPI mock API for the MVP validation page."""

import re
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.schemas.hs_graph import HSGraph
from core.duty_lookup import search

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "early_access.sqlite3"
GRAPH = HSGraph.load()

app = FastAPI(title="TarifeLab MVP API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class PreviewRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class EarlyAccessRequest(BaseModel):
    email: str = Field(max_length=254)
    consent: bool


@app.get("/api/health")
def health():
    return {"status": "ok", "graph_nodes": len(GRAPH.nodes) - 1}


@app.get("/api/hs/{code}")
def query_hs_code(code: str):
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=422, detail="HS code must contain exactly 6 digits")
    try:
        return GRAPH.classification_context(code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/preview")
def preview_product(payload: PreviewRequest):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Ürün açıklaması boş olamaz.")
    parsed = urlparse(query)
    if parsed.scheme in ("http", "https") and parsed.hostname:
        # URL is never fetched; only its visible path is used for the mock preview.
        query = unquote(parsed.path.replace("/", " ").replace("-", " ").replace("_", " "))
    candidates = [row for row in search(query) if len(row["hs6_code"]) == 6]
    return {
        "candidates": [
            {
                "code": row["hs6_code"],
                "description": row["description"],
                "rates": {country: row[f"{country.lower()}_mfn_pct"] or None for country in ("US", "EU", "UK", "CN")},
                "verified": row["last_verified"],
            }
            for row in candidates
        ],
        "notice": "Bu yalnızca 375 kodluk örnek tarifede İngilizce metin eşleşmesidir; resmi GTİP sınıflandırması değildir.",
    }


@app.post("/api/early-access", status_code=201)
def early_access(payload: EarlyAccessRequest):
    email = payload.email.strip().lower()
    if payload.consent is not True:
        raise HTTPException(status_code=400, detail="E-posta kaydı için açık rıza gereklidir.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=400, detail="Geçerli bir e-posta adresi girin.")
    with sqlite3.connect(DB) as db:
        db.execute("CREATE TABLE IF NOT EXISTS early_access (email TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        db.execute("INSERT OR IGNORE INTO early_access(email) VALUES (?)", (email,))
    return {"message": "Erken erişim listenize eklendiniz."}

