"""Testes da biblioteca de extração partilhada (scrapers/extractors.py).

Cada caso vem de texto real observado em anúncios PT. O objetivo não é
cobertura de linhas mas garantir que os erros que já custaram dados
errados na base não voltam: km lidos como 120 em vez de 120.000, "1.9 dCi"
ignorado, mensalidades apanhadas como preço, e por aí adiante.
"""
from __future__ import annotations

import pytest

from scrapers.extractors import (
    detect_damage,
    detect_national,
    enrich_listing,
    extract_co2,
    extract_color,
    extract_doors,
    extract_engine_size,
    extract_fuel,
    extract_horsepower,
    extract_km,
    extract_owners,
    extract_plate,
    extract_registration_date,
    extract_seats,
    extract_seller_type,
    extract_transmission,
    extract_vin,
    extract_warranty_months,
    extract_year,
    field_coverage,
    from_jsonld_vehicle,
    iter_jsonld,
    parse_pt_number,
)


class TestParsePtNumber:
    @pytest.mark.parametrize("raw,expected", [
        ("1.234,56", 1234.56),      # PT: ponto=milhar, vírgula=decimal
        ("1,234.56", 1234.56),      # EN
        ("120.000", 120000.0),      # 3 dígitos após ponto => milhar
        ("1.9", 1.9),               # 1 dígito => decimal
        ("12,5", 12.5),
        ("120 000", 120000.0),      # espaço é sempre milhar
        ("1 234 567", 1234567.0),
        ("12500", 12500.0),
        ("12.500 €", 12500.0),
        ("€ 8.950", 8950.0),
        (15000, 15000.0),
        (15000.5, 15000.5),
    ])
    def test_formats(self, raw, expected):
        assert parse_pt_number(raw) == pytest.approx(expected)

    @pytest.mark.parametrize("raw", [None, "", "sob consulta", "abc", "   "])
    def test_rejects_non_numeric(self, raw):
        assert parse_pt_number(raw) is None


class TestKm:
    @pytest.mark.parametrize("text,expected", [
        ("120.000 km", 120000),
        ("120 000 kms", 120000),
        ("120000Km", 120000),
        ("Quilometragem: 85.500", 85500),
        ("150 mil km", 150000),
        ("BMW 320d 2015 · 210.450 km · Diesel", 210450),
        ("apenas 9.800 kms", 9800),
    ])
    def test_extracts(self, text, expected):
        assert extract_km(text) == expected

    @pytest.mark.parametrize("text", [
        "",
        "Preço 12.500 €",          # sem menção a km
        "9.999.999 km",            # impossível: rejeita em vez de guardar
    ])
    def test_rejects(self, text):
        assert extract_km(text) is None


class TestYear:
    @pytest.mark.parametrize("text,expected", [
        ("Volkswagen Golf 2015", 2015),
        ("03/2018", 2018),
        ("Jan/2019", 2019),
        ("Registo 12-2020", 2020),
        # Revisão recente não pode ser confundida com o ano do carro.
        ("Audi A4 2012, revisão feita em 2024", 2012),
    ])
    def test_extracts(self, text, expected):
        assert extract_year(text) == expected

    def test_rejects_impossible_year(self):
        assert extract_year("Peugeot 2099") is None
        assert extract_year("modelo 1899") is None

    def test_registration_month(self):
        assert extract_registration_date("Matrícula 03/2018") == (2018, 3)
        assert extract_registration_date("Set/2021") == (2021, 9)
        assert extract_registration_date("Golf 2015") == (2015, None)


class TestEngine:
    @pytest.mark.parametrize("text,expected", [
        ("150 cv", 150),
        ("110cv diesel", 110),
        ("Potência: 190 HP", 190),
        ("81 kW", 110),                 # 81 * 1.35962 = 110.1
    ])
    def test_horsepower(self, text, expected):
        assert extract_horsepower(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("1968 cm3", 1968),
        ("1598cc", 1598),
        ("2.0 TDI", 2000),
        ("1.9 dCi", 1900),
        ("1,6 HDi", 1600),
        ("1.5 BlueHDi 130", 1500),
    ])
    def test_engine_size(self, text, expected):
        assert extract_engine_size(text) == expected

    def test_engine_size_ignores_year(self):
        # "Golf 2015" não pode virar 2015 cm3.
        assert extract_engine_size("Volkswagen Golf 2015") is None

    @pytest.mark.parametrize("text,expected", [
        ("120 g/km", 120.0),
        ("CO2: 99", 99.0),
        ("emissões 145 gr/km", 145.0),
    ])
    def test_co2(self, text, expected):
        assert extract_co2(text) == expected


class TestFuelTransmission:
    @pytest.mark.parametrize("text,expected", [
        ("Gasóleo", "diesel"),
        ("2.0 TDI", "diesel"),
        ("Gasolina", "gasolina"),
        ("1.4 TSI", "gasolina"),
        ("Híbrido Plug-in", "phev"),
        ("Hibrido", "hibrido"),
        ("100% Eléctrico", "eletrico"),
        ("GPL bi-fuel", "gpl"),
    ])
    def test_fuel(self, text, expected):
        assert extract_fuel(text) == expected

    def test_phev_wins_over_hybrid(self):
        # Ordem de regras: plug-in tem de ganhar a "híbrido".
        assert extract_fuel("Híbrido Plug-in recarregável") == "phev"

    @pytest.mark.parametrize("text,expected", [
        ("Caixa Manual", "manual"),
        ("Automática", "automatico"),
        ("DSG 7 velocidades", "automatico"),
        ("S-tronic", "automatico"),
        ("EDC", "automatico"),
    ])
    def test_transmission(self, text, expected):
        assert extract_transmission(text) == expected


class TestBodyAndSeller:
    def test_doors_seats(self):
        assert extract_doors("5 portas") == 5
        assert extract_seats("7 lugares") == 7

    def test_color(self):
        assert extract_color("Cor: Azul") == "azul"
        assert extract_color("Preto metalizado") == "preto"
        assert extract_color("cinza") == "cinzento"

    def test_seller_type(self):
        assert extract_seller_type("Auto Silva, Lda") == "profissional"
        assert extract_seller_type("Stand Automóveis do Norte") == "profissional"
        assert extract_seller_type("Vendedor particular") == "particular"
        assert extract_seller_type("João") is None

    def test_owners(self):
        assert extract_owners("Único dono") == 1
        assert extract_owners("2 proprietários") == 2
        assert extract_owners("Golf 2015") is None

    def test_warranty(self):
        assert extract_warranty_months("Garantia 12 meses") == 12
        assert extract_warranty_months("garantia de 2 anos") == 24
        assert extract_warranty_months("sem garantia") is None


class TestRisk:
    def test_severe_damage(self):
        result = detect_damage("Vendo BMW salvado, para peças")
        assert result["has_damage"] is True
        assert result["severity"] == "total"

    def test_cosmetic_damage(self):
        result = detect_damage("Pequenos riscos na chapa")
        assert result["has_damage"] is True
        assert result["severity"] == "cosmetico"

    def test_no_damage(self):
        assert detect_damage("Impecável, sempre em garagem")["has_damage"] is False

    def test_national_vs_import(self):
        assert detect_national("Viatura nacional, 1 dono") is True
        assert detect_national("Importado da Alemanha, por legalizar") is False
        assert detect_national("Volkswagen Golf 1.6 TDI") is None


class TestIdentifiers:
    def test_plate(self):
        assert extract_plate("Matrícula 12-AB-34") == "12-AB-34"
        assert extract_plate("AA-12-34") == "AA-12-34"
        assert extract_plate("sem matricula") is None

    def test_vin(self):
        assert extract_vin("WVWZZZ1KZAW123456") == "WVWZZZ1KZAW123456"
        # 17 dígitos não é um VIN.
        assert extract_vin("12345678901234567") is None


class TestJsonLd:
    HTML = """
    <html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Car",
     "name":"Volkswagen Golf 1.6 TDI",
     "url":"https://exemplo.pt/golf",
     "brand":{"@type":"Brand","name":"Volkswagen"},
     "model":"Golf",
     "vehicleTransmission":"Manual",
     "fuelType":"Diesel",
     "mileageFromOdometer":{"@type":"QuantitativeValue","value":"145000"},
     "modelDate":"2016",
     "numberOfDoors":5,
     "color":"Cinzento",
     "vehicleEngine":{"@type":"EngineSpecification",
        "engineDisplacement":{"value":1598},
        "enginePower":{"value":110,"unitCode":"KWT"}},
     "offers":{"@type":"Offer","price":"14500","priceCurrency":"EUR"}}
    </script>
    </head><body></body></html>
    """

    def test_parses_vehicle(self):
        nodes = [n for n in iter_jsonld(self.HTML)]
        assert nodes, "nenhum bloco JSON-LD encontrado"
        data = from_jsonld_vehicle(nodes[0])
        assert data["brand"] == "Volkswagen"
        assert data["model"] == "Golf"
        assert data["km"] == 145000
        assert data["year"] == 2016
        assert data["price"] == 14500.0
        assert data["currency"] == "EUR"
        assert data["fuel_type"] == "diesel"
        assert data["transmission"] == "manual"
        assert data["engine_size"] == 1598
        assert data["horsepower"] == 150       # 110 kW → 150 CV
        assert data["doors"] == 5

    def test_handles_graph_and_bad_json(self):
        html = """
        <script type="application/ld+json">NAO E JSON</script>
        <script type="application/ld+json">
        {"@graph":[{"@type":"Car","name":"Audi A4","offers":{"price":"20000"}}]}
        </script>
        """
        names = [n.get("name") for n in iter_jsonld(html) if n.get("name")]
        assert "Audi A4" in names

    def test_non_vehicle_node_is_ignored(self):
        assert from_jsonld_vehicle({"@type": "BreadcrumbList", "name": "x"}) == {}


class TestEnrichListing:
    def test_fills_missing_fields(self):
        listing = {
            "title": "BMW 320d Touring 2.0 190cv Automático 2017",
            "description": "Nacional, único dono, 145.000 km, garantia 12 meses",
        }
        enrich_listing(listing)
        assert listing["year"] == 2017
        assert listing["km"] == 145000
        assert listing["horsepower"] == 190
        assert listing["engine_size"] == 2000
        assert listing["fuel_type"] == "diesel"
        assert listing["transmission"] == "automatico"
        assert listing["is_national"] is True
        assert listing["num_owners"] == 1
        assert listing["warranty_months"] == 12

    def test_does_not_overwrite_structured_values(self):
        # O scraper leu km=200000 de um campo estruturado; o título diz outra
        # coisa. O campo estruturado tem de ganhar.
        listing = {"title": "Golf 2015 com 100.000 km", "km": 200000}
        enrich_listing(listing)
        assert listing["km"] == 200000

    def test_overwrite_flag(self):
        listing = {"title": "Golf 2015 com 100.000 km", "km": 200000}
        enrich_listing(listing, overwrite=True)
        assert listing["km"] == 100000

    def test_never_infers_price(self):
        # Um preço nunca pode nascer de regex sobre o corpo do anúncio.
        listing = {"title": "Golf 2015", "description": "desde 199 €/mês"}
        enrich_listing(listing)
        assert "price" not in listing

    def test_empty_listing_is_safe(self):
        assert enrich_listing({}) == {}


class TestFieldCoverage:
    def test_reports_coverage(self):
        listings = [
            {"brand": "BMW", "model": "320d", "year": 2017, "km": 100000,
             "fuel_type": "diesel", "transmission": "automatico",
             "horsepower": 190, "engine_size": 2000, "price": 20000},
            {"brand": "Audi", "model": "A4", "year": 2016, "km": 150000,
             "fuel_type": "diesel", "transmission": "manual",
             "horsepower": 150, "engine_size": 2000, "price": 18000},
        ]
        report = field_coverage(listings)
        assert report["total"] == 2
        assert report["coverage"]["km"] == 100.0
        assert report["critical_ok"] is True

    def test_detects_broken_scraper(self):
        # Cenário real: o site mudou o HTML e km/ano deixaram de ser lidos.
        listings = [{"brand": "BMW", "model": "320d", "price": 20000} for _ in range(10)]
        report = field_coverage(listings)
        assert report["critical_ok"] is False
        assert report["coverage"]["km"] == 0.0

    def test_empty(self):
        assert field_coverage([])["total"] == 0
