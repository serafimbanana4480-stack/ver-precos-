"""
Martelo Lightweight Scraper — leilões de veículos em Portugal.
Site: martelo.pt/veiculos  (agregador de leilões)
Padrão: requests + BeautifulSoup, segue o mesmo contrato de olx_lightweight.py:
    scrape_listings(vehicle_type='carros', max_listings=200) -> List[dict]
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
    "Volkswagen", "BMW", "Audi", "Renault", "Peugeot", "Citroën", "Citroen",
    "Ford", "Toyota", "Honda", "Nissan", "Hyundai", "Kia", "Fiat", "Seat",
    "SEAT", "Skoda", "Volvo", "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel",
    "Mini", "Smart", "Jeep", "Porsche", "Jaguar", "Lexus", "Subaru", "Tesla",
    "Cupra", "DS", "Lancia", "MG", "BYD", "Polestar", "Chevrolet", "Chrysler",
]

EURO_RE = re.compile(r"([\d\.\s]+)\s*€", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
KM_RE = re.compile(r"([\d\.\s]+)\s*km", re.IGNORECASE)


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
    # procura exata (case-insensitive) em qualquer posicao
    for b in BRANDS:
        if b.lower() in t:
            return b
    return None


BODY_TYPES = [
    "SUV", "Berlina", "Carrinha", "Monovolume", "Compacto", "Utilitário",
    "Conversível", "Coupé", "Pick-up", "Pick Up", "Todo-o-terreno",
    "Todo o Terreno", "Descapotável", "Familiar", "Citadino", "Executive",
    "Hatchback", "Crossover", "Break", "Furgão", "Furgoneta", "Van",
    "Cabrio", "Roadster", "Targa", "Sedan", "Sedã", "Station Wagon",
    "Cabriolet", "Sport", "Estate",
]


def _to_num(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    s = s.replace("\xa0", "").replace(".", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return None


def _clean_widgets(text: Optional[str]) -> str:
    """Remove emoji widgets e labels de preço/leilão do texto do card."""
    clean = text or ""
    clean = re.sub(r"📷.*?foto", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"🚗", " ", clean)
    clean = re.sub(r"📍[^€]*?(?=(Valor Base|Lance Atual)|$)", "", clean,
                   flags=re.IGNORECASE)  # localização vem ANTES dos preços
    clean = re.sub(r"(Valor Base|Lance Atual)\s*[\d\.\xa0\s]*€", " ",
                   clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _clean_model(title: str, brand: Optional[str]) -> str:
    """Extrai o modelo: remove marca, ano, km, preço e a cauda do leilão."""
    if not title:
        return "Unknown"
    t = title
    if brand and brand != "Unknown":
        idx = t.lower().find(brand.lower())
        if idx >= 0:
            t = t[idx + len(brand):]
    # corta a partir de 'V. Mínimo' (tudo o que se segue é metadata do leilão:
    # V. Abertura, ⏱️ Termina em, código LEIL_...)
    t = re.sub(r"V\. M[íi]nimo.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"Ano\s+\d{4}", "", t)
    t = re.sub(r"[\d\.\xa0\s]+km", "", t, flags=re.IGNORECASE)
    t = re.sub(r"[\d\.\xa0\s]+€", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^[-\s,–—\.€·]+|[-\s,–—\.€·]+$", "", t).strip()
    t = re.sub(r"\s+", " ", t).strip()
    return t[:120] or "Unknown"


def _km_guard(km: Optional[float]) -> Optional[int]:
    if km is None:
        return None
    km = int(round(km))
    return km if 0 < km <= 1_000_000 else None


class MarteloLightweight:
    """Scraper leve para martelo.pt (leilões de veículos)."""

    BASE_URL = "https://martelo.pt"
    LISTING = "https://martelo.pt/veiculos"

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
            url = f"{self.LISTING}?page={page}"
            try:
                resp = self.session.get(url, timeout=25)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("a.event-card")
                if not cards:
                    break
                for card in cards:
                    if len(listings) >= max_listings:
                        break
                    href = card.get("href", "")
                    if not href:
                        continue
                    url_abs = href if href.startswith("http") else self.BASE_URL + href
                    text = card.get_text(" ", strip=True)
                    clean = _clean_widgets(text)
                    if not clean:
                        continue
                    # Valor Base vs Lance Atual: preferir Lance Atual (preco real de mercado)
                    lance = None
                    base = None
                    for m in EURO_RE.finditer(clean):
                        val = _parse_eur(m.group(0))
                        if val:
                            ctx = clean[max(0, m.start()-25):m.start()].lower()
                            if "lance" in ctx:
                                lance = val
                            elif base is None:
                                base = val
                    price = lance or base
                    if not price or price <= 0:
                        continue
                    price_kind = "auction_current" if lance else "auction_start"
                    brand = _detect_brand(clean) or "Unknown"
                    ym = YEAR_RE.search(clean)
                    year = int(ym.group(0)) if ym else None
                    km_m = KM_RE.search(clean)
                    km = _km_guard(_to_num(km_m.group(1)) if km_m else None)
                    model = _clean_model(clean, brand)
                    listings.append({
                        "url": url_abs,
                        "source_id": url_abs,
                        "brand": brand,
                        "model": model,
                        "year": year,
                        "km": km,
                        "price": price,
                        "price_raw": str(price),
                        "currency": "EUR",
                        "price_kind": price_kind,
                        "vehicle_type": vehicle_type,
                        "title": clean[:500],
                        "location": None,
                        "is_auction": True,
                    })
                page += 1
                if page > 30:
                    break
                time.sleep(0.5)
            except Exception as e:
                logger.warning("[MARTELO] page %s err: %s", page, e)
                break
        return listings[:max_listings]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Martelo: {len(MarteloLightweight().scrape_listings(max_listings=20))} listings")
