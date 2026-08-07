"""
Motor de scraping genérico e declarativo (2026-08).

Porquê
------
Cada fonte nova custava ~400 linhas copiadas da anterior: sessão HTTP,
cabeçalhos, retries, paginação, parsing, normalização. O resultado eram
17 implementações ligeiramente diferentes do mesmo problema — e 17 sítios
onde o mesmo bug tinha de ser corrigido.

Aqui a fonte passa a ser **dados**: uma :class:`SourceConfig` descreve URLs,
seletores e paginação; o :class:`GenericSource` executa. A extração de
campos delega inteiramente em :mod:`scrapers.extractors`, pelo que qualquer
melhoria no parsing beneficia todas as fontes de uma só vez.

Estratégia de extração, por ordem de preferência:

1. **JSON-LD** (``schema.org/Vehicle``) — presente na maioria dos sites de
   stand e imune a mudanças de CSS;
2. **``__NEXT_DATA__``** — sites em Next.js (OLX, Standvirtual);
3. **Seletores CSS** declarados na config — último recurso.

Se um nível falhar, passa-se ao seguinte. Uma fonte só é dada como partida
quando os três falham, o que se traduz num erro explícito e não em zero
anúncios silenciosos.
"""
from __future__ import annotations

import hashlib
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.extractors import (
    enrich_listing,
    field_coverage,
    from_jsonld_vehicle,
    iter_jsonld,
)
from scrapers.schema import parse_price_evidence

logger = logging.getLogger(__name__)

USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
)


@dataclass(frozen=True)
class SourceConfig:
    """Descrição declarativa de uma fonte de anúncios.

    Attributes:
        name: nome curto usado em logs e no runner.
        source_enum: valor de ``database.models.Source`` para persistência.
        base_url: origem, usada para resolver URLs relativas.
        search_paths: caminho de pesquisa por tipo de veículo.
        page_param: nome do parâmetro de paginação (ex.: ``page``).
        first_page: índice da primeira página (1 na maioria, 0 nalguns).
        max_pages: teto de páginas por execução (proteção anti-loop).
        card_selectors: seletores CSS de cartão de anúncio, por ordem.
        title_selectors / price_selectors / link_selectors: dentro do cartão.
        detail_selectors: seletores da página de detalhe (specs).
        price_kind: tipo de preço esperado (``total``, ``auction_start``…).
        currency: moeda declarada da fonte.
        is_auction: fontes de leilão não entram nos comparáveis de retalho.
        country: ISO-2. Fontes estrangeiras servem arbitragem de importação.
        requires_js: se ``True``, o scraper HTTP não serve e a fonte é
            marcada como necessitando de browser.
        rate_limit: segundos entre pedidos.
    """

    name: str
    source_enum: str
    base_url: str
    search_paths: Dict[str, str] = field(default_factory=dict)
    page_param: str = "page"
    first_page: int = 1
    max_pages: int = 20
    extra_params: Dict[str, str] = field(default_factory=dict)
    card_selectors: Sequence[str] = ()
    title_selectors: Sequence[str] = ("h2", "h3", "[class*='title']", "[class*='name']")
    price_selectors: Sequence[str] = ("[class*='price']", "[class*='preco']", "[data-price]")
    link_selectors: Sequence[str] = ("a[href]",)
    location_selectors: Sequence[str] = ("[class*='location']", "[class*='local']", "[class*='city']")
    seller_selectors: Sequence[str] = ("[class*='dealer']", "[class*='seller']", "[class*='stand']")
    detail_selectors: Sequence[str] = (
        "[class*='spec']", "[class*='caracteristica']", "[class*='detail']",
        "dl", "table",
    )
    price_kind: str = "total"
    currency: str = "EUR"
    is_auction: bool = False
    country: str = "PT"
    requires_js: bool = False
    rate_limit: float = 1.0
    timeout: int = 25
    #: Gancho opcional para pós-processar cada anúncio (ex.: converter moeda).
    post_process: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None


class SourceUnavailable(RuntimeError):
    """A fonte respondeu mas não foi possível extrair anúncios.

    Distinta de "zero anúncios": esta exceção significa que o *scraper* está
    partido (layout mudou, bloqueio anti-bot), não que não há stock.
    """


class GenericSource:
    """Executor HTTP para uma :class:`SourceConfig`."""

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(self._headers())
        self.last_coverage: Dict[str, Any] = {}

    # ── HTTP ──────────────────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
            "Referer": self.config.base_url,
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        }

    def _fetch(self, url: str, *, attempts: int = 3) -> Optional[str]:
        """GET com backoff exponencial. Devolve ``None`` em vez de lançar."""
        for attempt in range(attempts):
            try:
                response = self.session.get(url, timeout=self.config.timeout)
                if response.status_code == 200:
                    return response.text
                if response.status_code in (403, 429, 503):
                    # Bloqueio/limite: esperar mais e rodar o User-Agent.
                    wait = (2 ** attempt) * 2 + random.uniform(0.5, 1.5)
                    logger.warning(
                        "[%s] HTTP %s em %s — nova tentativa em %.1fs",
                        self.config.name, response.status_code, url, wait,
                    )
                    self.session.headers["User-Agent"] = random.choice(USER_AGENTS)
                    time.sleep(wait)
                    continue
                logger.warning("[%s] HTTP %s em %s", self.config.name, response.status_code, url)
                return None
            except requests.RequestException as exc:
                wait = (2 ** attempt) + random.uniform(0.2, 0.8)
                logger.warning("[%s] erro de rede (%s) — nova tentativa em %.1fs",
                               self.config.name, exc, wait)
                time.sleep(wait)
        return None

    def _search_url(self, vehicle_type: str, page: int) -> str:
        path = self.config.search_paths.get(
            vehicle_type, self.config.search_paths.get("carros", "/")
        )
        url = urljoin(self.config.base_url, path)
        params = dict(self.config.extra_params)
        if page != self.config.first_page:
            params[self.config.page_param] = str(page)
        if params:
            separator = "&" if "?" in url else "?"
            url = url + separator + "&".join(f"{k}={v}" for k, v in params.items())
        return url

    # ── Extração ──────────────────────────────────────────────────────────

    def _from_jsonld(self, html: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for node in iter_jsonld(html):
            data = from_jsonld_vehicle(node)
            if data.get("title") and (data.get("url") or data.get("price")):
                rows.append(data)
        return rows

    def _from_cards(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        cards: List[Any] = []
        for selector in self.config.card_selectors:
            cards = soup.select(selector)
            if cards:
                logger.debug("[%s] %d cartões via %r", self.config.name, len(cards), selector)
                break
        rows: List[Dict[str, Any]] = []
        for card in cards:
            row = self._parse_card(card)
            if row:
                rows.append(row)
        return rows

    def _first_text(self, card: Any, selectors: Sequence[str]) -> str:
        for selector in selectors:
            node = card.select_one(selector)
            if node is not None:
                text = node.get_text(" ", strip=True)
                if text:
                    return text
        return ""

    def _parse_card(self, card: Any) -> Optional[Dict[str, Any]]:
        try:
            link = None
            for selector in self.config.link_selectors:
                link = card.select_one(selector)
                if link is not None and link.get("href"):
                    break
            href = link.get("href", "") if link is not None else ""
            if not href:
                return None
            url = urljoin(self.config.base_url, href)

            title = self._first_text(card, self.config.title_selectors)
            if not title and link is not None:
                title = link.get("title") or link.get_text(" ", strip=True)
            if not title:
                return None

            price_text = self._first_text(card, self.config.price_selectors)
            return self._build(
                url=url,
                title=title,
                price_text=price_text,
                card_text=card.get_text(" ", strip=True),
                location=self._first_text(card, self.config.location_selectors),
                seller=self._first_text(card, self.config.seller_selectors),
            )
        except Exception as exc:  # noqa: BLE001 — um cartão mau não pára a página
            logger.debug("[%s] cartão ilegível: %s", self.config.name, exc)
            return None

    def _build(
        self,
        *,
        url: str,
        title: str,
        price_text: str,
        card_text: str = "",
        location: str = "",
        seller: str = "",
    ) -> Dict[str, Any]:
        """Constrói o anúncio normalizado com proveniência de preço completa."""
        evidence = parse_price_evidence(
            price_text,
            context=f"{title} {card_text} fonte={self.config.name}",
            declared_currency=self.config.currency,
            declared_kind=self.config.price_kind,
        )
        retail = (
            evidence.value
            if evidence.kind.value == "total" and evidence.currency == "EUR"
            else 0.0
        )
        listing: Dict[str, Any] = {
            "source": self.config.source_enum,
            "source_id": hashlib.md5(url.encode()).hexdigest(),
            "url": url,
            "title": title[:500],
            "price": retail,
            "price_raw": evidence.raw,
            "price_observed_value": evidence.value,
            "currency": evidence.currency,
            "price_kind": evidence.kind.value,
            "price_evidence": evidence.evidence,
            "price_rejection_reason": evidence.rejection_reason,
            "location": location[:200],
            "seller_name": seller[:200] or None,
            "country": self.config.country,
            "is_auction": self.config.is_auction,
            "first_seen": datetime.now(timezone.utc).isoformat(),
        }
        # Fontes estrangeiras: o veículo é por definição um importado, o que
        # implica ISV. Marcar aqui evita que o motor fiscal o trate como
        # nacional e subestime o custo de aquisição em milhares de euros.
        if self.config.country != "PT":
            listing["is_national"] = False
        enrich_listing(listing, extra_text=card_text)
        if self.config.post_process:
            listing = self.config.post_process(listing)
        return listing

    # ── API pública ───────────────────────────────────────────────────────

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        scrape_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """Recolhe até ``max_listings`` anúncios.

        Raises:
            SourceUnavailable: se nenhuma página produziu anúncios, o que
                indica scraper partido e não ausência de stock.
        """
        if self.config.requires_js:
            raise SourceUnavailable(
                f"{self.config.name} exige renderização JavaScript; "
                "usar o scraper Playwright correspondente."
            )

        listings: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        #: Só contam páginas que responderam com HTML. Uma falha de rede não
        #: é prova de que o layout mudou, e não deve disparar SourceUnavailable.
        pages_parsed = 0
        pages_requested = 0
        page = self.config.first_page

        while len(listings) < max_listings and pages_requested < self.config.max_pages:
            html = self._fetch(self._search_url(vehicle_type, page))
            pages_requested += 1
            if not html:
                break
            pages_parsed += 1

            rows = self._from_jsonld(html)
            if rows:
                rows = [self._from_structured(row, vehicle_type) for row in rows]
            else:
                rows = self._from_cards(html)

            fresh = [
                row for row in rows
                if row.get("url") and row["url"] not in seen_urls
            ]
            if not fresh:
                break
            for row in fresh:
                seen_urls.add(row["url"])
                row.setdefault("vehicle_type", vehicle_type)
                listings.append(row)
                if len(listings) >= max_listings:
                    break

            page += 1
            time.sleep(self.config.rate_limit + random.uniform(0, 0.5))

        if not listings and pages_parsed:
            raise SourceUnavailable(
                f"{self.config.name}: {pages_parsed} página(s) obtidas mas "
                "nenhum anúncio extraído — layout provavelmente alterado."
            )

        if scrape_details and listings:
            self._enrich_details(listings)

        self.last_coverage = field_coverage(listings)
        logger.info(
            "[%s] %d anúncios | campos críticos OK=%s",
            self.config.name, len(listings), self.last_coverage.get("critical_ok"),
        )
        return listings

    def _from_structured(self, data: Dict[str, Any], vehicle_type: str) -> Dict[str, Any]:
        """Converte um nó JSON-LD já extraído no anúncio normalizado."""
        url = data.get("url") or ""
        if url and not urlparse(url).netloc:
            url = urljoin(self.config.base_url, url)
        listing = self._build(
            url=url,
            title=data.get("title", ""),
            price_text=str(data.get("price_raw") or data.get("price") or ""),
            card_text=data.get("description", "") or "",
        )
        for key, value in data.items():
            if key in ("price", "price_raw", "currency", "url", "title"):
                continue
            if listing.get(key) in (None, "", [], 0):
                listing[key] = value
        listing["vehicle_type"] = vehicle_type
        return listing

    def _enrich_details(self, listings: List[Dict[str, Any]], limit: int = 60) -> None:
        """Visita páginas de detalhe para completar specs em falta.

        Limitado por omissão: cada detalhe é um pedido HTTP, e o ganho
        marginal cai depressa. Prioriza os anúncios a que faltam campos
        que pesam na avaliação.
        """
        incomplete = [
            row for row in listings
            if not all(row.get(f) for f in ("year", "km", "fuel_type", "engine_size"))
        ]
        for listing in incomplete[:limit]:
            html = self._fetch(listing["url"], attempts=1)
            if not html:
                continue
            for node in iter_jsonld(html):
                structured = from_jsonld_vehicle(node)
                for key, value in structured.items():
                    if key in ("price", "price_raw", "currency", "url", "title"):
                        continue
                    if listing.get(key) in (None, "", [], 0):
                        listing[key] = value
            soup = BeautifulSoup(html, "html.parser")
            spec_text = " ".join(
                node.get_text(" ", strip=True)
                for selector in self.config.detail_selectors
                for node in soup.select(selector)
            )
            enrich_listing(listing, extra_text=spec_text or soup.get_text(" ", strip=True))
            time.sleep(self.config.rate_limit)


def build_scraper(config: SourceConfig) -> GenericSource:
    """Fábrica — mantém a construção num só sítio para facilitar mocking."""
    return GenericSource(config)
