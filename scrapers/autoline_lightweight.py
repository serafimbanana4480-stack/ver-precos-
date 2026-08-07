"""
Autoline Lightweight Scraper — leilões de veículos (autoline.pt).
Site: autoline.pt/-/leilao/carros--a9c1169
Padrão: requests + BeautifulSoup, scrape_listings(vehicle_type='carros', max_listings=200).
Lista ~73 páginas; cada listagem tem cards com ligação a detalhe onde
se extrai preço/ano/km. Para velocidade, extrai da própria listagem os
dados visíveis e faz GET de detalhe só quando necessário.
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
    "De Tomaso", "Lamborghini", "Ferrari", "Maserati", "Bentley", "Rolls Royce",
    "Bugatti", "McLaren", "Aston Martin", "Lotus", "Hummer", "Pontiac", "Saab",
    "Cadillac", "Dodge", "Ram", "GMC", "Infiniti", "Acura", "Isuzu", "Tata",
    "Mahindra", "Proton", "Perodua", "Lada", "Zastava", "Yugo", "Ssangyong",
]

# A lookbehind exclui letras além de dígitos: sem isso, "Renault ZOE R90 150 €"
# casava "90 150" (o "90" vem de "R90") e produzia um preço de 90.150 €.
EURO_RE = re.compile(r"(?<![A-Za-z\d])(\d{1,3}(?:[\.\xa0 ]\d{3})+|\d+)\s*€",
                     re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
KM_RE = re.compile(r"(?<!\d)([\d\.\xa0\s]+?)\s*km", re.IGNORECASE)

# Preço plausível para leilão de carros em PT (evita concatenações tipo
# "Peugeot 5008 22.580 €" → 500822580, onde o regex apanhava dígitos do modelo).
PRICE_MIN, PRICE_MAX = 50, 500_000

# ---------------------------------------------------------------------------
# Guardas de qualidade (auditoria 06/08/2026)
# ---------------------------------------------------------------------------
# O autoline.pt é um agregador pan-europeu, não um portal português. A auditoria
# de 1283 registos recolhidos mostrou:
#
#   * 33% dos anúncios são suecos (SEK) e 1% dinamarqueses (DKK) — não são
#     preços do mercado português e não devem entrar em nenhuma valorização;
#   * 43% dos preços "extraídos com sucesso" ficavam abaixo de 800 €, porque o
#     regex apanhava designações de motor ("Dacia Duster 1.5 dCi 150 €" -> 150);
#   * o número do modelo colava-se ao preço: "Peugeot 407 500 €" -> 407.500 €,
#     "Peugeot 308 100 €" -> 308.100 €, "Renault ZOE R90 150 €" -> 90.150 €.
#
# Só 22,5% dos registos tinham preço, e cerca de metade desses estavam errados.
# As guardas abaixo rejeitam esses casos em vez de os deixar entrar na base.

FOREIGN_CURRENCIES = ("SEK", "DKK", "NOK", "PLN", "CZK", "HUF", "RON", "BGN",
                      "CHF", "GBP", "ISK")

# Um carro de leilão em Portugal, mesmo salvado, raramente fica abaixo disto.
# Abaixo deste valor o número é quase sempre uma cilindrada, potência ou taxa.
PRICE_PLAUSIBLE_MIN = 800

# Acima disto num agregador de leilões é quase sempre concatenação de modelo.
PRICE_PLAUSIBLE_MAX = 250_000


def _has_foreign_currency(text: str) -> bool:
    """Anúncio cotado em moeda estrangeira — não é mercado português."""
    return any(re.search(rf"\b{c}\b", text or "", re.IGNORECASE)
               for c in FOREIGN_CURRENCIES)


def _price_is_plausible(price: Optional[float], title: str) -> bool:
    """Rejeita os modos de falha conhecidos do parser de preço do Autoline."""
    if price is None or not (PRICE_PLAUSIBLE_MIN <= price <= PRICE_PLAUSIBLE_MAX):
        return False

    title = title or ""
    digits = str(int(price))

    # Modo 1 — prefixo é a designação do modelo, isolada no título:
    #   "Peugeot 407 500 €" -> 407500, e "407" aparece como token.
    for n in (3, 4):
        if len(digits) > n and re.search(rf"\b{digits[:n]}\b(?!\d)", title):
            return False

    # Modo 2 — o título contém um valor em euros mais pequeno que é sufixo do
    # número lido: "Renault ZOE R90 ... 150 €" -> 90150, sufixo "150".
    # O prefixo restante ("90") vem colado a uma letra ("R90"), por isso o
    # modo 1 não o apanha.
    for m in EURO_RE.finditer(title):
        inner = (m.group(1) or "").replace("\xa0", "").replace(".", "").replace(" ", "")
        if (inner and inner != digits and len(inner) < len(digits)
                and digits.endswith(inner)):
            return False

    return True


def _num(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    s = s.replace("\xa0", "").replace(".", "").replace(" ", "")
    try:
        return float(s)
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


def _clean_title(title: str) -> str:
    """Limpa o título do Autoline: remove 'carro', ano, matrícula, body, escrapalia, vendedor."""
    t = title or ""
    t = re.sub(r"^(carro|Carro)\s+", "", t)
    t = re.sub(r"\b(Año|Ano)\s+(19|20)\d{2}\b", "", t)
    t = re.sub(r"Matr[íi]cula[^–\-]*", "", t)
    t = re.sub(r"Tipo de carro[çc]aria.*$", "", t)
    t = re.sub(r"Escrapalia.*$", "", t)
    t = re.sub(r"Contacte o vendedor.*$", "", t)
    # remove a cauda comum a todos ('Leilão Carro', combustível, país, vendedor)
    t = re.sub(r"Leil[ãa]o Carro.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"Combust[íi]vel.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^(1\s+)(?=[A-Z])", "", t)  # numeracao de ordem '1 Mercedes...'
    t = re.sub(r"\s+", " ", t).strip()
    return t


# Delimitadores que marcam o fim do modelo e início das especificações
_MODEL_STOP = [
    r"\b\d[\d\.\xa0\s]*€",              # preço (ex: 150 €, 1 044 €)
    r"\|",
    r"\b(19|20)\d{2}\b",
    r"km",
    r"A[ñn]o",
    r"Matr[íi]cula",
    r"VIN",
    r"Exp\.",
    r"Di[ée]sel",
    r"Gasolina",
    r"Combust[íi]vel",
    r"Pot[êe]ncia",
    r"Carro\s+\d{4}",                    # 'Carro 1971'
    r"Tipo de",
    r"Escrapalia",
    r"Contacte",
    r"Sem impostos",
    r"Crossover|Hatchback|Berlina|Carrinha|Monovolume|SUV|Convers[íi]vel|"
    r"Coup[ée]|Cabrio|Roadster|Familiar|Citadino|Pick[\s-]?up|"
    r"Todo[\s-]?o[\s-]?terreno|Furg[ãa]o|Van|Estate|Break|Sed[ãa]n|Station",
    r"\b\d{4}\s+[A-ZÀ-Ú]{2,3}\b",       # matrícula tipo 6923 MCW
    r"\b\d{1,4}\s+[A-ZÀ-Ú]{1,3}\b",     # matrícula curta tipo 60 L, 2970 LTL
]


def _cut_model(t: str) -> str:
    """Corta o modelo no primeiro delimitador de especificações/preço."""
    best = len(t)
    for pat in _MODEL_STOP:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m and m.start() < best:
            best = m.start()
    return t[:best]


def _clean_model(title: str, brand: Optional[str]) -> str:
    """Extrai modelo: remove marca, duplicação (2ª ocorrência) e specs/preço."""
    if not title:
        return "Unknown"
    t = title
    # 1) remove a marca do início
    if brand and brand != "Unknown":
        idx = t.lower().find(brand.lower())
        if idx >= 0:
            t = t[idx + len(brand):]
    # 2) título duplicado? corta na 2ª ocorrência da marca (início da repetição)
    if brand and brand != "Unknown":
        j = t.lower().find(brand.lower())
        if j > 0:
            t = t[:j]
    # 3) se NÃO estava duplicado, corta no 1º delimitador de specs/preço
    if not (brand and brand != "Unknown" and j > 0):
        t = _cut_model(t)
    t = re.sub(r"[\d\.\xa0\s]+€", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^[-\s,–—\.€·]+|[-\s,–—\.€·]+$", "", t).strip()
    t = re.sub(r"\s+", " ", t).strip()
    return t[:120] or "Unknown"


def _km_guard(km: Optional[float]) -> Optional[int]:
    if km is None:
        return None
    km = int(round(km))
    return km if 0 < km <= 1_000_000 else None


class AutolineLightweight:
    """Scraper leve para autoline.pt (leilões de carros)."""

    BASE_URL = "https://www.autoline.pt"
    LISTING = "https://www.autoline.pt/-/leilao/carros--a9c1169"

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

    def _parse_detail(self, url: str) -> Dict[str, Any]:
        try:
            r = self.session.get(url, timeout=30)
            if r.status_code != 200:
                return {}
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(" ", strip=True)
            price_m = EURO_RE.search(text)
            price = _num(price_m.group(1)) if price_m else None
            if price is not None and not (PRICE_MIN <= price <= PRICE_MAX):
                price = None
            ym = YEAR_RE.search(text)
            year = int(ym.group(0)) if ym else None
            km_m = KM_RE.search(text)
            km = int(_num(km_m.group(1))) if km_m else None
            return {"price": price, "year": year, "km": km}
        except Exception as e:
            logger.warning("[AUTOLINE] detail err %s: %s", url, e)
            return {}

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
                resp = self.session.get(url, timeout=30)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("sl-item, .sl-item, a[href*='/leilao/carros/']")
                if not cards:
                    break
                seen = set()
                for card in cards:
                    if len(listings) >= max_listings:
                        break
                    a = card if card.name == "a" else card.select_one("a")
                    if not a or not a.get("href"):
                        continue
                    href = a.get("href")
                    # ignorar links de categoria (terminam em --a9c1169btXXXXX)
                    if re.search(r"--a9c1169", href or ""):
                        continue
                    if href in seen:
                        continue
                    seen.add(href)
                    url_abs = href if href.startswith("http") else self.BASE_URL + href
                    text = card.get_text(" ", strip=True)
                    title = _clean_title(text)
                    if not title:
                        continue
                    # Anúncio em moeda estrangeira: o autoline.pt agrega leilões
                    # suecos e dinamarqueses. Não são mercado português.
                    if _has_foreign_currency(text):
                        continue
                    # preco: 'X €' esta no titulo. A matricula foi removida, logo
                    # os numeros restantes sao preco ou kms. Pegar o ultimo € valido.
                    price = None
                    for m in EURO_RE.finditer(title):
                        v = _to_num(m.group(1))
                        if v and PRICE_MIN <= v <= PRICE_MAX:
                            price = v
                    # Guarda contra os modos de falha conhecidos (ver topo do
                    # ficheiro): designações de motor lidas como preço e número
                    # do modelo concatenado com o preço.
                    if not _price_is_plausible(price, title):
                        continue
                    # ano: 'Año 2001' ou 'Ano 2001'.
                    # group(2) é apenas o século ("19"/"20") — usar o match todo.
                    ym = re.search(r"(Año|Ano)\s+((?:19|20)\d{2})", text)
                    year = int(ym.group(2)) if ym else None
                    # km: pode vir como numero gigante (ex 202097810) -> ignora se >1M
                    km_m = KM_RE.search(text)
                    km = _km_guard(_to_num(km_m.group(1)) if km_m else None)
                    # marca: primeiro token conhecido
                    brand = _detect_brand(title) or "Unknown"
                    model = _clean_model(title, brand)
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
                        "price_kind": "auction_start",
                        "vehicle_type": vehicle_type,
                        "title": title[:500],
                        "location": None,
                        "is_auction": True,
                    })
                page += 1
                if page > 73:
                    break
                time.sleep(0.5)
            except Exception as e:
                logger.warning("[AUTOLINE] page %s err: %s", page, e)
                break
        return listings[:max_listings]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Autoline: {len(AutolineLightweight().scrape_listings(max_listings=20))} listings")
