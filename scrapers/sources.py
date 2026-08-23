"""
Registo central de fontes (2026-08).

Substitui as ~500 linhas de funções ``run_*`` duplicadas em
``parallel_runner.py`` por um registo único. Adicionar uma fonte passa a ser
acrescentar uma entrada — sem copiar sessão HTTP, retries nem parsing.

Duas famílias de fonte:

``retalho`` (PT)
    Preços pedidos em stands e particulares. São a base dos comparáveis:
    definem quanto o carro se **vende**.

``leilao`` / ``importacao``
    Onde o carro se **compra** abaixo do mercado. É aqui que nasce a margem:
    um leilão judicial ou um stand alemão fixam o preço de aquisição, e o
    mercado português fixa o preço de saída. A diferença, depois de ISV,
    transporte e recondicionamento, é o lucro real.

Fontes estrangeiras ficam marcadas com ``country != "PT"`` e
``is_national=False``, o que faz o motor fiscal cobrar ISV automaticamente —
sem isso o lucro de um importado aparece inflacionado em milhares de euros.
"""
from __future__ import annotations

import logging
import inspect
from typing import Callable, Dict, List, Optional

from scrapers.generic_source import GenericSource, SourceConfig, build_scraper

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Retalho nacional
# ─────────────────────────────────────────────────────────────────────────────

STANDVIRTUAL = SourceConfig(
    name="StandvirtualLight",
    source_enum="STANDVIRTUAL",
    base_url="https://www.standvirtual.com",
    search_paths={"carros": "/carros", "motos": "/motos"},
    page_param="page",
    max_pages=25,
    card_selectors=(
        "article[data-id]",
        "article[data-testid='listing-ad']",
        "[data-testid='search-results'] article",
        "article",
    ),
    title_selectors=("h2 a", "h2", "[data-testid='ad-title']", "h1"),
    price_selectors=(
        "[data-testid='ad-price']",
        "h3[class*='price']",
        "[class*='Price']",
        "[class*='price']",
    ),
    location_selectors=("[data-testid='location-date']", "[class*='location']"),
    seller_selectors=("[data-testid='seller-link']", "[class*='seller']", "[class*='dealer']"),
    rate_limit=2.0,
)

CAETANO = SourceConfig(
    name="CaetanoUsados",
    source_enum="CAETANO",
    base_url="https://www.caetanoauto.pt",
    search_paths={"carros": "/usados"},
    page_param="pagina",
    max_pages=15,
    card_selectors=(
        "[class*='vehicle-card']", "[class*='car-card']",
        "article[class*='vehicle']", ".product-item", "article",
    ),
    rate_limit=1.5,
)

SANTOGAL = SourceConfig(
    name="SantogalUsados",
    source_enum="SANTOGAL",
    base_url="https://usados.santogal.pt",
    search_paths={"carros": "/viaturas"},
    page_param="page",
    max_pages=15,
    card_selectors=(
        "[class*='vehicle-item']", "[class*='car-item']",
        "[class*='viatura']", "article",
    ),
    rate_limit=1.5,
)

# ─────────────────────────────────────────────────────────────────────────────
# Novas fontes de retalho nacional (2026-08-06)
# ─────────────────────────────────────────────────────────────────────────────

SPOTICAR_PT = SourceConfig(
    name="Spoticar_PT",
    source_enum="SPOTICAR_PT",
    base_url="https://www.spoticar.pt",
    search_paths={"carros": "/carros"},
    page_param="p",
    max_pages=15,
    card_selectors=(
        "article[class*='listing']", "div[class*='product']",
        "div[class*='vehicule']", "article",
    ),
    title_selectors=("h3", "h2", "[class*='title']", "[class*='nom']"),
    price_selectors=("[class*='prix']", "[class*='price']", "[class*='montant']"),
    location_selectors=("[class*='localisation']", "[class*='location']"),
    currency="EUR",
    country="PT",
    rate_limit=1.5,
)

COMPRAR_CARRO = SourceConfig(
    name="ComprarCarro",
    source_enum="COMPRAR_CARRO",
    base_url="https://www.compramososeu.carro.pt",
    search_paths={"carros": "/carros"},
    page_param="page",
    max_pages=10,
    card_selectors=("[class*='vehicle']", "[class*='car']", "[class*='offer']", "article"),
    title_selectors=("h2", "h3", "[class*='title']"),
    price_selectors=("[class*='prix']", "[class*='price']", "[class*='preco']"),
    currency="EUR",
    country="PT",
    rate_limit=2.0,
)

AUTOUNCLE_PT = SourceConfig(
    name="AutoUncle_PT",
    source_enum="AUTOUNCLE_PT",
    base_url="https://www.auto-uncle.pt",
    search_paths={"carros": "/carros"},
    page_param="page",
    max_pages=15,
    card_selectors=("[class*='listing']", "[class*='car']", "[class*='offer']", "article"),
    title_selectors=("h2", "h3", "[class*='title']"),
    price_selectors=("[class*='prix']", "[class*='price']", "[class*='preco']"),
    currency="EUR",
    country="PT",
    rate_limit=2.0,
)

AUTOSCOUT24_PT = SourceConfig(
    name="AutoScout24PT",
    source_enum="AUTOSCOUT24_PT",
    base_url="https://www.autoscout24.pt",
    search_paths={"carros": "/lst"},
    extra_params={"sort": "price", "desc": "0", "cy": "P", "atype": "C"},
    page_param="page",
    max_pages=10,
    card_selectors=("article[class*='cldt-summary']", "article[data-guid]", "article"),
    title_selectors=("h2", "[class*='title']"),
    price_selectors=("[class*='Price_price']", "[class*='price']", "p[class*='Price']"),
    country="PT",
    rate_limit=2.5,
)

#: Fontes de retalho nacional — definem o preço de venda alcançável.
RETAIL_SOURCES = (STANDVIRTUAL, CAETANO, SANTOGAL, SPOTICAR_PT, COMPRAR_CARRO, AUTOUNCLE_PT, AUTOSCOUT24_PT)


# ─────────────────────────────────────────────────────────────────────────────
# Leilões (preço de aquisição abaixo do mercado)
# ─────────────────────────────────────────────────────────────────────────────

ELEILOES = SourceConfig(
    name="ELeiloes",
    source_enum="ELEILOES",
    base_url="https://www.e-leiloes.pt",
    # Leilões eletrónicos judiciais: a maior fonte de veículos vendidos
    # sistematicamente abaixo do valor de mercado em Portugal.
    search_paths={"carros": "/Home/PesquisaBens"},
    extra_params={"categoria": "veiculos"},
    page_param="pagina",
    max_pages=10,
    card_selectors=("[class*='bem']", "[class*='lote']", "[class*='card']", "article", "tr"),
    price_selectors=(
        "[class*='valor']", "[class*='base']", "[class*='licitacao']", "[class*='price']",
    ),
    price_kind="auction_start",
    is_auction=True,
    rate_limit=2.0,
)

#: Fontes de leilão — definem o preço de aquisição.
AUCTION_SOURCES = (ELEILOES,)


# ─────────────────────────────────────────────────────────────────────────────
# Importação (arbitragem transfronteiriça)
# ─────────────────────────────────────────────────────────────────────────────

# O mercado alemão é 15-30% mais barato que o português no mesmo carro,
# porque a Alemanha não tem ISV. A margem real só aparece depois de somar
# ISV + transporte + legalização — que é exatamente o que o motor fiscal
# calcula. Sem estas fontes, esse arbitrage é invisível.
AUTOSCOUT24_DE = SourceConfig(
    name="AutoScout24DE",
    source_enum="AUTOSCOUT24_DE",
    base_url="https://www.autoscout24.de",
    search_paths={"carros": "/lst"},
    extra_params={"sort": "price", "desc": "0", "cy": "D", "atype": "C"},
    page_param="page",
    max_pages=15,
    card_selectors=("article[class*='cldt-summary']", "article[data-guid]", "article"),
    title_selectors=("h2", "[class*='title']"),
    price_selectors=("[class*='Price_price']", "[class*='price']", "p[class*='Price']"),
    country="DE",
    rate_limit=2.5,
)

AUTOSCOUT24_ES = SourceConfig(
    name="AutoScout24ES",
    source_enum="AUTOSCOUT24_ES",
    base_url="https://www.autoscout24.es",
    search_paths={"carros": "/lst"},
    extra_params={"sort": "price", "desc": "0", "cy": "E", "atype": "C"},
    page_param="page",
    max_pages=10,
    card_selectors=("article[class*='cldt-summary']", "article[data-guid]", "article"),
    title_selectors=("h2", "[class*='title']"),
    price_selectors=("[class*='Price_price']", "[class*='price']", "p[class*='Price']"),
    country="ES",
    rate_limit=2.5,
)

AUTOSCOUT24_FR = SourceConfig(
    name="AutoScout24FR",
    source_enum="AUTOSCOUT24_FR",
    base_url="https://www.autoscout24.fr",
    search_paths={"carros": "/lst"},
    extra_params={"sort": "price", "desc": "0", "cy": "F", "atype": "C"},
    page_param="page",
    max_pages=10,
    card_selectors=("article[class*='cldt-summary']", "article[data-guid]", "article"),
    title_selectors=("h2", "[class*='title']"),
    price_selectors=("[class*='Price_price']", "[class*='price']", "p[class*='Price']"),
    country="FR",
    rate_limit=2.5,
)


# ─────────────────────────────────────────────────────────────────────────────
# Novas fontes estrangeiras — arbitragem de importação (2026-08-06)
# ─────────────────────────────────────────────────────────────────────────────

SPOTICAR = SourceConfig(
    name="Spoticar",
    source_enum="SPOTICAR",
    base_url="https://www.spoticar.fr",
    search_paths={"carros": "/voitures"},
    page_param="p",
    max_pages=15,
    card_selectors=(
        "article[class*='listing']", "div[class*='product']",
        "div[class*='vehicule']", "article",
    ),
    title_selectors=("h3", "h2", "[class*='title']", "[class*='nom']"),
    price_selectors=("[class*='prix']", "[class*='price']", "[class*='montant']"),
    location_selectors=("[class*='localisation']", "[class*='location']"),
    currency="EUR",
    country="FR",
    rate_limit=2.0,
)

MILANUNCIOS = SourceConfig(
    name="Milanuncios",
    source_enum="MILANUNCIOS",
    base_url="https://www.milanuncios.com",
    search_paths={"carros": "/coches"},
    page_param="p",
    max_pages=20,
    card_selectors=(
        "div[class*='aditem']", "article[class*='ad']",
        "div[class*='listado']", "div[class*='anuncio']", "article",
    ),
    title_selectors=("h2", "h3", "[class*='titulo']"),
    price_selectors=("[class*='precio']", "[class*='price']", "[class*='precio-label']"),
    location_selectors=("[class*='ubicacion']", "[class*='provincia']", "[class*='localidad']"),
    currency="EUR",
    country="ES",
    rate_limit=1.8,
)

COCHES_NET = SourceConfig(
    name="CochesNet",
    source_enum="COCHES_NET",
    base_url="https://www.coches.net",
    search_paths={"carros": "/coches"},
    page_param="pg",
    max_pages=20,
    card_selectors=(
        "article[class*='anuncio']", "div[class*='anuncio']",
        "article[class*='item']", "article",
    ),
    title_selectors=("h2", "h3", "[class*='titulo']"),
    price_selectors=("[class*='precio']", "[class*='price']"),
    location_selectors=("[class*='localidad']", "[class*='provincia']", "[class*='zona']"),
    currency="EUR",
    country="ES",
    rate_limit=1.8,
)

ARGUS_FR = SourceConfig(
    name="Argus_FR",
    source_enum="ARGUS_FR",
    base_url="https://www.argus-assurances.fr",
    search_paths={"carros": "/cotes-voitures"},
    page_param="page",
    max_pages=15,
    card_selectors=("[class*='fiche']", "[class*='voiture']", "table tbody tr", "article"),
    title_selectors=("h2", "h3", "[class*='title']"),
    price_selectors=("[class*='valeur']", "[class*='prix']", "[class*='price']"),
    currency="EUR",
    country="FR",
    rate_limit=2.0,
)

#: Fontes estrangeiras — arbitragem de importação.
IMPORT_SOURCES = (
    AUTOSCOUT24_DE, AUTOSCOUT24_ES, AUTOSCOUT24_FR,
    SPOTICAR, MILANUNCIOS, COCHES_NET, ARGUS_FR,
)


# ─────────────────────────────────────────────────────────────────────────────
# Registo
# ─────────────────────────────────────────────────────────────────────────────

ALL_CONFIGS: Dict[str, SourceConfig] = {
    config.name.lower(): config
    for config in (*RETAIL_SOURCES, *AUCTION_SOURCES, *IMPORT_SOURCES)
}

#: Fontes já existentes no projeto, implementadas com scrapers dedicados.
#: Ficam aqui apenas para o runner as descobrir por um único caminho.
LEGACY_SOURCES: Dict[str, Dict[str, object]] = {
    "carplus": {"module": "scrapers.carplus_lightweight", "cls": "CarplusLightweightScraper", "enum": "CARPLUS"},
    "autouncle": {"module": "scrapers.autouncle_lightweight", "cls": "AutoUncleLightweight", "enum": "AUTOUNCLE"},
    "piscapisca": {"module": "scrapers.piscapisca_lightweight", "cls": "PiscaPiscaLightweight", "enum": "PISCAPISCA", "max": 50},
    "leilosoc": {"module": "scrapers.leilosoc_lightweight", "cls": "LeilosocLightweight", "enum": "LEILOSOC", "auction": True},
    # VPAuto has a dedicated async/Playwright adapter.  It is registered here
    # through an explicit normalizer instead of appearing as an unsupported
    # enum in audit scripts.
    "vpauto": {"module": "scrapers.ground_truth_scraper", "cls": "VPAutoScraper", "enum": "VPAUTO", "auction": True, "ground_truth": True},
    "autopt": {"module": "scrapers.autopt_lightweight", "cls": "AutoPtLightweightScraper", "enum": "AUTOPT"},
    "olx": {"module": "scrapers.olx_lightweight", "cls": "OLXLightweight", "enum": "OLX"},
    "mcoutinho": {"module": "scrapers.mcoutinho_lightweight", "cls": "McoutinhoLightweight", "enum": "MCOUTINHO"},
    "autohub": {"module": "scrapers.autohub_lightweight", "cls": "AutohubLightweight", "enum": "AUTOHUB"},
    "martelo": {"module": "scrapers.martelo_lightweight", "cls": "MarteloLightweight", "enum": "MARTELO", "auction": True},
    "autoline": {"module": "scrapers.autoline_lightweight", "cls": "AutolineLightweight", "enum": "AUTOLINE", "auction": True},
    "penhorado": {"module": "scrapers.penhorado_lightweight", "cls": "PenhoradoLightweight", "enum": "PENHORADO", "auction": True},
    "autoscout24": {"module": "scrapers.autoscout24_lightweight", "cls": "AutoScout24Lightweight", "enum": "AUTOSCOUT24"},
    "custojusto": {"module": "scrapers.custojusto_scraper", "cls": "CustoJustoScraper", "enum": "CUSTOJUSTO", "async": True},
    # New European sources (2026-08-06) — lightweight scrapers for API/SSR sites
    "autohero": {"module": "scrapers.autohero_lightweight", "cls": "AutoHeroLightweight", "enum": "AUTOHERO", "country": "FR"},
    "leboncoin": {"module": "scrapers.leboncoin_lightweight", "cls": "LeBonCoinLightweight", "enum": "LEBONCOIN", "country": "FR"},
    "wallapop": {"module": "scrapers.wallapop_lightweight", "cls": "WallapopLightweight", "enum": "WALLAPOP", "country": "ES"},
    "lacentrale": {"module": "scrapers.lacentrale_lightweight", "cls": "LaCentraleLightweight", "enum": "LACENTRALE", "country": "FR"},
    "lacentrale_es": {"module": "scrapers.lacentrale_es_lightweight", "cls": "LaCentraleESLightweight", "enum": "LACENTRALE_ES", "country": "ES"},
    "idealista_autos": {"module": "scrapers.idealista_autos_lightweight", "cls": "IdealistaAutosLightweight", "enum": "IDEALISTA_AUTOS", "country": "ES"},
}


def get_source(name: str) -> Optional[GenericSource]:
    """Instancia uma fonte declarativa pelo nome (case-insensitive)."""
    config = ALL_CONFIGS.get(name.lower())
    return build_scraper(config) if config else None


def list_sources(*, include_legacy: bool = True) -> List[str]:
    """Nomes de todas as fontes conhecidas."""
    names = sorted(ALL_CONFIGS)
    if include_legacy:
        names += sorted(LEGACY_SOURCES)
    return names


def sources_by_role(role: str) -> List[SourceConfig]:
    """Fontes por papel: ``retalho`` | ``leilao`` | ``importacao``."""
    return {
        "retalho": list(RETAIL_SOURCES),
        "leilao": list(AUCTION_SOURCES),
        "importacao": list(IMPORT_SOURCES),
    }.get(role, [])


def build_legacy_callable(name: str, max_listings: int, vehicle_type: str) -> Callable[[], List[dict]]:
    """Devolve um callable síncrono para um scraper dedicado existente.

    Uniformiza a chamada — alguns scrapers são async, outros não — para que
    o runner os trate exatamente como as fontes declarativas.
    """
    spec = LEGACY_SOURCES[name.lower()]
    cap = int(spec.get("max") or max_listings)
    limit = min(max_listings, cap)

    def _run() -> List[dict]:
        import importlib
        import asyncio

        module = importlib.import_module(str(spec["module"]))
        cls = getattr(module, str(spec["cls"]))
        instance = cls()

        def publish_status(rows: List[dict]) -> List[dict]:
            # A callable attribute lets the resilience layer and bounded
            # audit preserve blocked/timeout/degraded instead of collapsing
            # every empty result into ``empty``.
            _run.last_status = getattr(
                instance,
                "last_status",
                "ok" if rows else "empty",
            )
            _run.last_error = getattr(instance, "last_error", None)
            return rows

        async def close_async() -> None:
            close = getattr(instance, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result
                return
            session = getattr(instance, "session", None)
            close_session = getattr(session, "close", None)
            if callable(close_session):
                result = close_session()
                if inspect.isawaitable(result):
                    await result

        if spec.get("ground_truth"):
            async def _scrape_ground_truth() -> List[dict]:
                try:
                    if hasattr(instance, "__aenter__"):
                        async with instance:
                            raw = await instance.scrape(max_listings=limit)
                    else:
                        raw = await instance.scrape(max_listings=limit)
                finally:
                    await close_async()
                normalized: List[dict] = []
                for item in raw:
                    observed = item.starting_price or item.adjudication_price
                    kind = "auction_start" if item.starting_price else "auction_adjudicated"
                    normalized.append({
                        "source": getattr(item.source, "value", item.source),
                        "source_id": item.source_id,
                        "url": item.url,
                        "vehicle_type": getattr(item.vehicle_type, "value", item.vehicle_type),
                        "brand": item.brand,
                        "model": item.model,
                        "version": item.version,
                        # ``0`` is the storage sentinel for a non-retail
                        # auction observation; never use it as a retail price.
                        "price": 0.0,
                        "price_raw": f"{observed} EUR" if observed else None,
                        "price_observed_value": observed or None,
                        "price_kind": kind,
                        "currency": "EUR",
                        "year": item.year or None,
                        "km": item.km,
                        "horsepower": item.horsepower,
                        "engine_size": item.engine_size,
                        "fuel_type": getattr(item.fuel_type, "value", item.fuel_type),
                        "transmission": getattr(item.transmission, "value", item.transmission),
                        "color": item.color,
                        "location": item.location,
                        "district": item.district,
                        "title": item.title,
                        "description": item.description,
                        "images": item.images,
                        "seller_type": item.seller_type,
                        "seller_name": item.seller_name,
                        "has_damage": item.has_damage,
                    })
                return normalized

            return publish_status(asyncio.run(_scrape_ground_truth()))
        if spec.get("async"):
            async def _scrape_async() -> List[dict]:
                try:
                    return await instance.scrape_listings(
                        vehicle_type,
                        max_listings=limit,
                    )
                finally:
                    await close_async()

            return publish_status(asyncio.run(_scrape_async()))
        try:
            rows = instance.scrape_listings(vehicle_type, max_listings=limit)
            return publish_status(rows)
        finally:
            # Synchronous legacy adapters own their per-run requests session.
            close = getattr(instance, "close", None)
            if callable(close):
                close()
            else:
                session = getattr(instance, "session", None)
                close_session = getattr(session, "close", None)
                if callable(close_session):
                    close_session()

    return _run
