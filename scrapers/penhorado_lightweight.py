"""
Penhorado Lightweight Scraper — carros penhorados / leilões de Finanças.
Site: penhorado.pt/tag/carro-penhorado  (WordPress, artigos por anúncio)
Padrão: requests + BeautifulSoup, scrape_listings(vehicle_type='carros', max_listings=200).
"""
from __future__ import annotations

import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BRANDS = [
    "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz", "Mercedes",
    "Volkswagen", "VW", "BMW", "Audi", "Renault", "Peugeot", "Citroën", "Citroen",
    "Ford", "Toyota", "Honda", "Nissan", "Hyundai", "Kia", "Fiat", "Seat",
    "SEAT", "Skoda", "Volvo", "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel",
    "Mini", "Smart", "Jeep", "Porsche", "Jaguar", "Lexus", "Subaru", "Tesla",
    "Cupra", "DS", "Lancia", "MG", "BYD", "Polestar", "Chevrolet", "Chrysler",
]

EURO_RE = re.compile(r"([\d\.\s]+)\s*€", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _parse_eur(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    m = EURO_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(" ", ""))
    except ValueError:
        return None


def _detect_brand(title: str) -> Optional[str]:
    if not title:
        return None
    t = title.lower()
    for b in BRANDS:
        if b.lower() in t:
            return b
    return None


def _clean_penhorado_title(raw: str) -> str:
    """Remove 'Penhorada em Leilão por X€', 'por X euros', 'by admin', 'Posted in ...'."""
    t = raw or ""
    t = re.sub(r"Penhorada em Leil[ãa]o por\s*[\d\.\s]*€", "", t, flags=re.IGNORECASE)
    t = re.sub(r"[A-Za-zà-úÀ-ÚçÇ]+(?:\s+[A-Za-zà-úÀ-ÚçÇ]+)*?\s+por\s*[\d\.\s]*(euros?|€)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"by admin", "", t, flags=re.IGNORECASE)
    t = re.sub(r"Posted in.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


BODY_TYPES = [
    "SUV", "Berlina", "Carrinha", "Monovolume", "Compacto", "Utilitário",
    "Conversível", "Coupé", "Pick-up", "Pick Up", "Todo-o-terreno",
    "Todo o Terreno", "Descapotável", "Familiar", "Citadino", "Executive",
    "Hatchback", "Crossover", "Break", "Furgão", "Furgoneta", "Van",
    "Cabrio", "Roadster", "Targa", "Sedan", "Sedã", "Station Wagon",
    "Cabriolet", "Sport", "Estate",
]


def _penhorado_model(title: str, brand: Optional[str]) -> str:
    if not title:
        return "Unknown"
    t = title
    if brand and brand != "Unknown":
        idx = t.lower().find(brand.lower())
        if idx >= 0:
            t = t[idx + len(brand):]
    # remove toda a cauda de leilão/penhora
    t = re.sub(r"Penhorad[oa].*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"em Leil[ãa]o.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"por\s*[\d\.\s]*(euros?|€).*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"licite.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"[\d\.\xa0\s]+€", "", t, flags=re.IGNORECASE)
    for bt in BODY_TYPES:
        t = re.sub(rf"\b{re.escape(bt)}\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^[-\s,–—\.€]+|[-\s,–—\.€]+$", "", t).strip()
    t = re.sub(r"\s+", " ", t).strip()
    return t[:120] or "Unknown"


def _find_title_link(art) -> Optional[Any]:
    """Link do título do post (não o link de categoria 'Carros Penhorados')."""
    sel = art.select_one("h1 a, h2 a, h3 a, .entry-title a, .post-title a")
    if sel:
        return sel
    for link in art.find_all("a"):
        txt = link.get_text(" ", strip=True)
        href = link.get("href", "") or ""
        if not txt:
            continue
        if "/tag/" in href or "/category/" in href:
            continue
        if txt.lower() in ("carros penhorados", "penhorado"):
            continue
        if len(txt) > 8:
            return link
    return None


class PenhoradoLightweight:
    """Scraper leve para penhorado.pt (carros penhorados / leilão Finanças)."""

    BASE_URL = "https://penhorado.pt"
    LISTING = "https://penhorado.pt/tag/carro-penhorado"

    def __init__(self) -> None:
        self.session = requests.Session()
        self._rotate_headers()

    def _rotate_headers(self) -> None:
        self.session.headers.update({
            "User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            ]),
            "Accept-Language": "pt-PT,pt;q=0.9",
        })

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 200,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        listings: List[Dict[str, Any]] = []
        page = 1
        while len(listings) < max_listings:
            url = f"{self.LISTING}/page/{page}" if page > 1 else self.LISTING
            try:
                resp = self.session.get(url, timeout=25)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                articles = soup.select("article")
                if not articles:
                    break
                for art in articles:
                    if len(listings) >= max_listings:
                        break
                    a = _find_title_link(art)
                    if not a:
                        continue
                    href = a.get("href", "")
                    if not href:
                        continue
                    url_abs = href if href.startswith("http") else self.BASE_URL + href
                    # titulo real do anuncio (do link <a>), nao a tag/categoria da pagina
                    raw_title = a.get_text(" ", strip=True)
                    title = _clean_penhorado_title(raw_title)
                    if not title or len(title) < 5:
                        continue
                    brand = _detect_brand(title) or "Unknown"
                    price = _parse_eur(art.get_text(" ", strip=True))
                    if not price or price <= 0:
                        continue
                    ym = YEAR_RE.search(title)
                    year = int(ym.group(0)) if ym else None
                    model = _penhorado_model(title, brand)
                    listings.append({
                        "url": url_abs,
                        "source_id": url_abs,
                        "brand": brand,
                        "model": model,
                        "year": year,
                        "km": None,
                        "price": price,
                        "title": title[:500],
                        "location": None,
                        "is_auction": True,
                    })
                page += 1
                if page > 20:
                    break
                time.sleep(0.5)
            except Exception as e:
                logger.warning("[PENHORADO] page %s err: %s", page, e)
                break
        return listings[:max_listings]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Penhorado: {len(PenhoradoLightweight().scrape_listings(max_listings=20))} listings")
