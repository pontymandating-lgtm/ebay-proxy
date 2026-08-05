# -*- coding: utf-8 -*-
"""Proxy eBay Finding API — contourne les blocages FAI (Bytel/Free).

Déployé sur Render (gratuit). L'app JAKO / Vinted Coteur appellent ce
proxy au lieu de svcs.ebay.com directement, car le FAI de certains
utilisateurs bloque l'API eBay (HTTP 418).
"""
import os

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="eBay Price Proxy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EBAY_APP_ID = os.getenv("EBAY_APP_ID", "").strip()
EBAY_URL = "https://svcs.ebay.com/services/search/FindingService/v1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9",
}


@app.get("/api/health")
def health():
    return {"status": "ok", "ebay_key": bool(EBAY_APP_ID)}


@app.get("/api/prices")
def prices(q: str = "", isbn: str = "", limit: int = 20):
    if not EBAY_APP_ID:
        return {"status": "no_key", "detail": "EBAY_APP_ID non configuré côté serveur"}
    keywords = (q or "").strip()
    if not keywords and isbn:
        keywords = isbn
    if not keywords:
        return {"status": "error", "detail": "Paramètre q ou isbn requis"}

    params = {
        "OPERATION-NAME": "findCompletedItems",
        "SERVICE-VERSION": "1.13.0",
        "SECURITY-APPNAME": EBAY_APP_ID,
        "RESPONSE-DATA-FORMAT": "JSON",
        "REST-PAYLOAD": "",
        "paginationInput.entriesPerPage": str(limit),
        "itemFilter(0).name": "SoldItemsOnly",
        "itemFilter(0).value": "true",
        "sortOrder": "EndTimeSoonest",
        "keywords": keywords,
    }
    try:
        r = httpx.get(EBAY_URL, params=params, headers=HEADERS, timeout=25)
    except Exception as exc:
        return {"status": "error", "detail": f"Requête eBay échouée : {exc}"}

    if r.status_code != 200:
        return {"status": "error", "detail": f"eBay HTTP {r.status_code}"}

    try:
        d = r.json()
    except Exception:
        return {"status": "error", "detail": "Réponse eBay non-JSON"}

    resp = d.get("findCompletedItemsResponse") or [{}]
    resp = resp[0] if isinstance(resp, list) else resp
    if (resp.get("ack") or [""])[0] != "Success":
        errs = resp.get("errorMessage", [{}])
        if isinstance(errs, list) and errs:
            msg = (errs[0].get("error", [{}])[0] if isinstance(errs[0].get("error"), list)
                   else errs[0].get("error", {}))
            detail = msg.get("message", "Erreur eBay inconnue")
        else:
            detail = "Erreur eBay inconnue"
        return {"status": "error", "detail": detail}

    items = ((resp.get("searchResult") or [{}])[0].get("item")) or []
    out = []
    for it in items:
        st = (it.get("sellingStatus") or [{}])[0]
        price = (st.get("convertedCurrentPrice") or [{}])[0].get("value")
        cond = (it.get("condition") or [{}])[0]
        info = (it.get("listingInfo") or [{}])[0]
        try:
            price = float(price) if price is not None else None
        except (TypeError, ValueError):
            price = None
        out.append({
            "titre": it.get("title") or "",
            "prix": price,
            "etat": cond.get("conditionDisplayName") or "",
            "date": (info.get("endTime") or "")[:10],
        })
    return {"status": "ok", "count": len(out), "items": out}
