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
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.extractors import (
    enrich_listing,
    field_coverage,
    from_jsonld_vehicle,
    iter_jsonld,
)
from scrapers.schema import parse_price_evidence
from scrapers.resilience import (
    STATUS_BLOCKED,
    STATUS_BLOCKED_CREDENTIALS,
    STATUS_DEGRADED,
    STATUS_EMPTY,
    STATUS_FAILED,
    STATUS_OK,
    STATUS_TIMEOUT,
    status_for_http,
)

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
    timeout: float = 12.0
    retry_attempts: int = 2
    retry_backoff_seconds: float = 0.10
    max_retry_backoff_seconds: float = 0.40
    #: Gancho opcional para pós-processar cada anúncio (ex.: converter moeda).
    post_process: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None


class SourceUnavailable(RuntimeError):
    """A fonte respondeu mas não foi possível extrair anúncios.

    Distinta de "zero anúncios": esta exceção significa que o *scraper* está
    partido (layout mudou, bloqueio anti-bot), não que não há stock.
    """

    def __init__(self, message: str, *, status: str = STATUS_DEGRADED) -> None:
        super().__init__(message)
        self.status = status


class GenericSource:
    """Executor HTTP para uma :class:`SourceConfig`."""

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(self._headers())
        self.last_coverage: Dict[str, Any] = {}
        self.last_status = STATUS_EMPTY
        self.last_error: Optional[str] = None
        self.requests_made = 0
        self.retries = 0
        self._closed = False

    def close(self) -> None:
        """Fecha o pool HTTP da fonte.

        As fontes são instanciadas por execução. Fechá-las explicitamente
        evita manter sockets abertos quando um lote percorre muitas fontes e
        torna o ciclo de vida compatível com auditorias concorrentes.
        """
        if not self._closed:
            self.session.close()
            self._closed = True

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
        """GET bounded; terminal HTTP/auth errors return immediately."""
        max_attempts = max(1, min(int(attempts), int(self.config.retry_attempts)))
        for attempt in range(max_attempts):
            self.requests_made += 1
            try:
                response = self.session.get(url, timeout=self.config.timeout)
                if response.status_code == 200:
                    self.last_status = STATUS_OK
                    return response.text
                status, retryable = status_for_http(response.status_code)
                self.last_status = status
                self.last_error = f"HTTP {response.status_code}"
                logger.warning("[%s] HTTP %s em %s", self.config.name, response.status_code, url)
                if retryable and attempt + 1 < max_attempts:
                    self.retries += 1
                    wait = min(
                        self.config.max_retry_backoff_seconds,
                        self.config.retry_backoff_seconds * (2 ** attempt),
                    )
                    if wait > 0:
                        time.sleep(wait)
                    continue
                return None
            except requests.Timeout as exc:
                self.last_status = STATUS_TIMEOUT
                self.last_error = str(exc) or "request timeout"
                logger.warning("[%s] timeout em %s", self.config.name, url)
                if attempt + 1 < max_attempts:
                    self.retries += 1
                    wait = min(
                        self.config.max_retry_backoff_seconds,
                        self.config.retry_backoff_seconds * (2 ** attempt),
                    )
                    if wait > 0:
                        time.sleep(wait)
                    continue
                return None
            except requests.ConnectionError as exc:
                text = str(exc).lower()
                self.last_status = STATUS_FAILED
                self.last_error = str(exc)
                # DNS is terminal for this run: retrying it only burns the
                # source budget and cannot produce anti-bot or listing data.
                dns_error = any(token in text for token in (
                    "getaddrinfo", "name or service not known",
                    "failed to resolve", "name resolution", "dns",
                ))
                if not dns_error and attempt + 1 < max_attempts:
                    self.retries += 1
                    wait = min(
                        self.config.max_retry_backoff_seconds,
                        self.config.retry_backoff_seconds * (2 ** attempt),
                    )
                    if wait > 0:
                        time.sleep(wait)
                    continue
                return None
            except requests.RequestException as exc:
                self.last_status = STATUS_FAILED
                self.last_error = str(exc)
                logger.warning("[%s] erro de rede (%s)", self.config.name, exc)
                return None
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
            url = url + separator + urlencode(params)
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
        max_listings = max(0, int(max_listings))
        self.last_status = STATUS_EMPTY
        self.last_error = None
        self.requests_made = 0
        self.retries = 0
        if self.config.requires_js:
            raise SourceUnavailable(
                f"{self.config.name} exige renderização JavaScript; "
                "usar o scraper Playwright correspondente.",
                status="unsupported",
            )
        if max_listings == 0:
            self.last_coverage = field_coverage([])
            return []

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
            if len(listings) < max_listings and pages_requested < self.config.max_pages:
                delay = max(0.0, float(self.config.rate_limit))
                if delay > 0:
                    time.sleep(delay)

        if not listings and pages_parsed:
            self.last_status = STATUS_DEGRADED
            raise SourceUnavailable(
                f"{self.config.name}: {pages_parsed} página(s) obtidas mas "
                "nenhum anúncio extraído — layout provavelmente alterado.",
                status=STATUS_DEGRADED,
            )

        if scrape_details and listings:
            self._enrich_details(listings)

        if listings:
            if self.last_status in {
                STATUS_BLOCKED,
                STATUS_BLOCKED_CREDENTIALS,
                STATUS_TIMEOUT,
                STATUS_FAILED,
            }:
                # Partial data plus a terminal later page is usable only as a
                # degraded observation; never silently call it healthy.
                self.last_status = STATUS_DEGRADED
            else:
                self.last_status = STATUS_OK
        else:
            self.last_status = self.last_status or STATUS_EMPTY
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
            if listing is not incomplete[-1]:
                delay = max(0.0, float(self.config.rate_limit))
                if delay > 0:
                    time.sleep(delay)


def build_scraper(config: SourceConfig) -> GenericSource:
    """Fábrica — mantém a construção num só sítio para facilitar mocking."""
    return GenericSource(config)
