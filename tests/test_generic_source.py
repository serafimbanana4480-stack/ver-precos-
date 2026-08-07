"""Testes do motor de scraping declarativo.

Não fazem rede: cada teste injeta HTML fixo através de ``_fetch``. O objetivo
é fixar o contrato do motor — o que ele extrai, o que rejeita e, sobretudo,
quando falha de forma ruidosa em vez de devolver zero anúncios em silêncio.
"""
from __future__ import annotations

from typing import List, Optional

import pytest

from scrapers.generic_source import GenericSource, SourceConfig, SourceUnavailable
from scrapers.sources import ALL_CONFIGS, LEGACY_SOURCES, get_source, sources_by_role


CARD_HTML = """
<html><body>
<div class="results">
  <article class="vehicle-card">
    <a href="/viatura/1"><h2 class="title">Volkswagen Golf 1.6 TDI 115cv</h2></a>
    <span class="price">14.900 €</span>
    <span class="location">Porto</span>
    <span class="dealer">Auto Silva, Lda</span>
    <p>2017 · 145.000 km · Diesel · Manual</p>
  </article>
  <article class="vehicle-card">
    <a href="/viatura/2"><h2 class="title">BMW 320d Touring 2.0 190cv</h2></a>
    <span class="price">21.500 €</span>
    <span class="location">Lisboa</span>
    <p>2019 · 98.000 km · Automático</p>
  </article>
</div>
</body></html>
"""

JSONLD_HTML = """
<html><head>
<script type="application/ld+json">
[{"@type":"Car","name":"Audi A4 2.0 TDI","url":"https://exemplo.pt/a4",
  "brand":{"name":"Audi"},"model":"A4","modelDate":"2018",
  "mileageFromOdometer":{"value":"120000"},
  "vehicleTransmission":"Automatic","fuelType":"Diesel",
  "offers":{"price":"22500","priceCurrency":"EUR"}}]
</script>
</head><body></body></html>
"""

EMPTY_HTML = "<html><body><p>Sem resultados</p></body></html>"


def make_config(**overrides) -> SourceConfig:
    base = dict(
        name="TesteFonte",
        source_enum="TESTE",
        base_url="https://exemplo.pt",
        search_paths={"carros": "/usados"},
        card_selectors=("article.vehicle-card",),
        title_selectors=("h2.title",),
        price_selectors=("span.price",),
        location_selectors=("span.location",),
        seller_selectors=("span.dealer",),
        rate_limit=0.0,
        max_pages=2,
    )
    base.update(overrides)
    return SourceConfig(**base)


class FakeSource(GenericSource):
    """GenericSource com ``_fetch`` substituído por páginas pré-definidas."""

    def __init__(self, config: SourceConfig, pages: List[Optional[str]]) -> None:
        super().__init__(config)
        self._pages = list(pages)
        self.requested: List[str] = []

    def _fetch(self, url: str, *, attempts: int = 3) -> Optional[str]:
        self.requested.append(url)
        return self._pages.pop(0) if self._pages else None


class TestCardParsing:
    def test_extracts_all_fields(self):
        source = FakeSource(make_config(), [CARD_HTML, EMPTY_HTML])
        rows = source.scrape_listings("carros", max_listings=10)
        assert len(rows) == 2

        golf = rows[0]
        assert golf["url"] == "https://exemplo.pt/viatura/1"
        assert golf["title"].startswith("Volkswagen Golf")
        assert golf["price"] == 14900.0
        assert golf["currency"] == "EUR"
        assert golf["price_kind"] == "total"
        assert golf["location"] == "Porto"
        assert golf["seller_type"] == "profissional"   # "Lda" ⇒ stand
        assert golf["year"] == 2017
        assert golf["km"] == 145000
        assert golf["fuel_type"] == "diesel"
        assert golf["transmission"] == "manual"
        assert golf["horsepower"] == 115
        assert golf["engine_size"] == 1600
        assert golf["vehicle_type"] == "carros"

    def test_second_card(self):
        source = FakeSource(make_config(), [CARD_HTML, EMPTY_HTML])
        bmw = source.scrape_listings("carros", max_listings=10)[1]
        assert bmw["price"] == 21500.0
        assert bmw["year"] == 2019
        assert bmw["km"] == 98000
        assert bmw["transmission"] == "automatico"
        assert bmw["fuel_type"] == "diesel"      # "320d" ⇒ gasóleo
        assert bmw["seller_name"] is None

    def test_respects_max_listings(self):
        source = FakeSource(make_config(), [CARD_HTML])
        assert len(source.scrape_listings("carros", max_listings=1)) == 1

    def test_deduplicates_across_pages(self):
        # A mesma página devolvida duas vezes (paginação em loop) não pode
        # duplicar anúncios nem entrar em ciclo infinito.
        source = FakeSource(make_config(), [CARD_HTML, CARD_HTML, CARD_HTML])
        rows = source.scrape_listings("carros", max_listings=50)
        assert len(rows) == 2


class TestJsonLd:
    def test_prefers_structured_data(self):
        source = FakeSource(make_config(), [JSONLD_HTML, EMPTY_HTML])
        rows = source.scrape_listings("carros", max_listings=10)
        assert len(rows) == 1
        a4 = rows[0]
        assert a4["brand"] == "Audi"
        assert a4["km"] == 120000
        assert a4["year"] == 2018
        assert a4["price"] == 22500.0
        assert a4["transmission"] == "automatico"


class TestFailureModes:
    def test_raises_when_layout_breaks(self):
        # A página respondeu 200 mas nenhum cartão casou: o scraper está
        # partido. Tem de falhar alto, não devolver [] como se não houvesse
        # stock — foi assim que fontes ficaram mortas sem ninguém notar.
        source = FakeSource(make_config(), [EMPTY_HTML])
        with pytest.raises(SourceUnavailable, match="layout"):
            source.scrape_listings("carros", max_listings=10)

    def test_network_failure_returns_empty(self):
        # Falha de rede é diferente: não há evidência de layout partido.
        source = FakeSource(make_config(), [None])
        assert source.scrape_listings("carros", max_listings=10) == []

    def test_requires_js_is_explicit(self):
        source = FakeSource(make_config(requires_js=True), [CARD_HTML])
        with pytest.raises(SourceUnavailable, match="JavaScript"):
            source.scrape_listings("carros", max_listings=10)

    def test_bad_card_does_not_kill_page(self):
        html = """
        <article class="vehicle-card">sem link nem titulo</article>
        <article class="vehicle-card">
          <a href="/ok"><h2 class="title">Seat Ibiza 1.0 TSI 2020</h2></a>
          <span class="price">12.000 €</span>
        </article>
        """
        source = FakeSource(make_config(), [html, EMPTY_HTML])
        rows = source.scrape_listings("carros", max_listings=10)
        assert len(rows) == 1
        assert rows[0]["price"] == 12000.0


class TestPricingProvenance:
    def test_monthly_price_is_not_treated_as_total(self):
        # Uma mensalidade de financiamento nunca pode virar preço do carro.
        html = """
        <article class="vehicle-card">
          <a href="/x"><h2 class="title">Renault Clio 2019</h2></a>
          <span class="price">desde 149 €/mês</span>
        </article>
        """
        source = FakeSource(make_config(), [html, EMPTY_HTML])
        row = source.scrape_listings("carros", max_listings=5)[0]
        assert row["price"] == 0.0
        assert row["price_kind"] == "monthly"
        assert row["price_rejection_reason"]

    def test_auction_source_marks_price_kind(self):
        html = """
        <article class="vehicle-card">
          <a href="/lote/9"><h2 class="title">Opel Corsa 2016</h2></a>
          <span class="price">Valor base: 3.500 €</span>
        </article>
        """
        config = make_config(price_kind="auction_start", is_auction=True)
        source = FakeSource(config, [html, EMPTY_HTML])
        row = source.scrape_listings("carros", max_listings=5)[0]
        # Um preço de leilão não é retalho: não pode alimentar comparáveis.
        assert row["price"] == 0.0
        assert row["price_kind"] == "auction_start"
        assert row["is_auction"] is True

    def test_foreign_source_flags_import(self):
        # Sem esta marca o motor fiscal trata um carro alemão como nacional
        # e ignora o ISV — o maior custo isolado de uma importação.
        config = make_config(country="DE")
        source = FakeSource(config, [CARD_HTML, EMPTY_HTML])
        row = source.scrape_listings("carros", max_listings=5)[0]
        assert row["is_national"] is False
        assert row["country"] == "DE"


class TestCoverage:
    def test_reports_coverage(self):
        source = FakeSource(make_config(), [CARD_HTML, EMPTY_HTML])
        source.scrape_listings("carros", max_listings=10)
        assert source.last_coverage["total"] == 2
        assert source.last_coverage["coverage"]["km"] == 100.0


class TestUrlBuilding:
    def test_pagination_and_params(self):
        config = make_config(extra_params={"sort": "price"}, page_param="pagina")
        source = FakeSource(config, [CARD_HTML, CARD_HTML, EMPTY_HTML])
        source.scrape_listings("carros", max_listings=50)
        assert source.requested[0] == "https://exemplo.pt/usados?sort=price"
        assert "pagina=2" in source.requested[1]


class TestRegistry:
    def test_declarative_sources_are_wellformed(self):
        for name, config in ALL_CONFIGS.items():
            assert config.base_url.startswith("https://"), name
            assert config.search_paths, name
            assert config.card_selectors, name
            assert config.rate_limit > 0, f"{name}: rate limit 0 convida a bloqueio"

    def test_get_source(self):
        assert get_source("eleiloes") is not None
        assert get_source("nao-existe") is None

    def test_roles_are_populated(self):
        assert sources_by_role("retalho")
        assert sources_by_role("leilao")
        assert sources_by_role("importacao")

    def test_foreign_sources_are_marked(self):
        for config in sources_by_role("importacao"):
            assert config.country != "PT", config.name

    def test_auction_sources_are_marked(self):
        for config in sources_by_role("leilao"):
            assert config.is_auction, config.name
            assert config.price_kind != "total", config.name

    def test_every_source_maps_to_db_enum(self):
        from database.models import Source

        valid = {s.value for s in Source}
        for name, config in ALL_CONFIGS.items():
            assert config.source_enum in valid, f"{name} → {config.source_enum}"
        for name, spec in LEGACY_SOURCES.items():
            assert spec["enum"] in valid, f"{name} → {spec['enum']}"


class TestNewEuropeanSources:
    """Smoke tests for declarative configs added in 2026-08-06."""

    def test_spoticar_pt_config(self):
        config = get_source("spoticar_pt")
        assert config is not None
        assert config.config.country == "PT"

    def test_spoticar_fr_import(self):
        config = get_source("spoticar")
        assert config is not None
        assert config.config.country == "FR"
        assert config.config.name.lower() == "spoticar"

    def test_milanuncios_es_import(self):
        config = get_source("milanuncios")
        assert config is not None
        assert config.config.country == "ES"

    def test_coches_net_es_import(self):
        config = get_source("cochesnet")
        assert config is not None
        assert config.config.country == "ES"

    def test_autoscout24_pt_retail(self):
        config = get_source("autoscout24pt")
        assert config is not None
        assert config.config.country == "PT"
        assert config.config.search_paths["carros"] == "/lst"

    def test_argus_fr_import(self):
        config = get_source("argus_fr")
        assert config is not None
        assert config.config.country == "FR"

    def test_comprar_carro_pt_retail(self):
        config = get_source("comprarcarro")
        assert config is not None
        assert config.config.country == "PT"

    def test_auto_UNCLE_pt_retail(self):
        config = get_source("autouncle_pt")
        assert config is not None
        assert config.config.country == "PT"

    def test_legacy_scrapers_registered(self):
        assert "autohero" in LEGACY_SOURCES
        assert "leboncoin" in LEGACY_SOURCES
        assert "wallapop" in LEGACY_SOURCES
        assert "lacentrale" in LEGACY_SOURCES
        assert "lacentrale_es" in LEGACY_SOURCES
        assert "idealista_autos" in LEGACY_SOURCES

    def test_legacy_scrapers_import(self):
        """Lightweight scrapers can be imported and instantiated."""
        from scrapers.sources import LEGACY_SOURCES, build_legacy_callable

        for key in ("autohero", "leboncoin", "wallapop", "lacentrale", "lacentrale_es", "idealista_autos"):
            spec = LEGACY_SOURCES[key]
            import importlib
            module = importlib.import_module(str(spec["module"]))
            cls = getattr(module, str(spec["cls"]))
            instance = cls()
            assert hasattr(instance, "scrape_listings")

    def test_spoticar_pt_extracts_card(self):
        config = get_source("spoticar_pt")
        html = """
        <html><body>
        <article class="listing-card">
          <a href="/voiture/123" class="listing-link">
            <h3 class="title">Peugeot 308 1.2 PureTech 110ch</h3>
            <div class="prix">18 500 €</div>
            <span class="localisation">Lisbon</span>
          </a>
        </article>
        </body></html>
        """
        source = FakeSource(config.config, [html, EMPTY_HTML])
        rows = source.scrape_listings("carros", max_listings=10)
        assert len(rows) >= 1
        row = rows[0]
        assert "Peugeot" in row["title"]
        assert row["price"] == 18500.0
        assert row["country"] == "PT"

    def test_milanuncios_es_extracts_card(self):
        config = get_source("milanuncios")
        html = """
        <html><body>
        <div class="aditem">
          <a href="/anuncio/bmw-series-1-2018">
            <h2 class="titulo">BMW Serie 1 116d 115cv</h2>
            <div class="precio">19.900 €</div>
            <span class="ubicacion">Barcelona</span>
          </a>
        </div>
        </body></html>
        """
        source = FakeSource(config.config, [html, EMPTY_HTML])
        rows = source.scrape_listings("carros", max_listings=10)
        assert len(rows) >= 1
        row = rows[0]
        assert "BMW" in row["title"]
        assert row["country"] == "ES"
        assert row["price"] == 19900.0
