"""Large, deterministic edge-case matrix for parser and source contracts."""

from types import SimpleNamespace

import pytest

from app.api.websockets import vehicle_update_payload
from scrapers.schema import PriceKind, parse_price_evidence
from utils.source_normalize import normalize_source
from validation.normalizers import normalize_vehicle_data


_TOTAL_CASES = [
    ("500 €", 500.0),
    ("1.250 €", 1_250.0),
    ("10.500,50 €", 10_500.50),
    ("€ 9000", 9_000.0),
    ("15000", 15_000.0),
    ("450.000 €", 450_000.0),
    ("10,000.00 EUR", 10_000.0),
    ("10 500 EUR", 10_500.0),
]

_SAFE_CONTEXTS = [
    "BMW 320d 2020 80.000 km",
    "Peugeot 5008 2019",
    "Renault Clio 1.5 dCi",
    "Ferrari F8",
    "Toyota Corolla Hybrid",
    "Volkswagen Golf 7 110 cv",
    "Mercedes-Benz A 180",
    "Honda Civic 2018",
    "Audi Q4 e-tron",
    "Ford Focus carrinha",
    "Dacia Sandero Stepway",
    "Volvo XC60 T8",
    "Nissan Leaf 40 kWh",
    "Kia Sportage GT-Line",
    "SEAT Leon FR",
    "Skoda Octavia 2.0 TDI",
    "Tesla Model 3",
    "Mini Cooper S",
    "Porsche 911 Carrera",
    "Fiat 500 Hybrid",
]

_TOTAL_MATRIX = [
    (raw, context, expected)
    for raw, expected in _TOTAL_CASES
    for context in _SAFE_CONTEXTS
]


@pytest.mark.parametrize("raw,context,expected", _TOTAL_MATRIX)
def test_total_price_matrix_preserves_numeric_evidence(raw, context, expected):
    result = parse_price_evidence(raw, context=context)

    assert result.value == expected
    assert result.currency == "EUR"
    assert result.kind is PriceKind.TOTAL
    assert result.rejection_reason is None


_NON_RETAIL_CASES = [
    ("desde 199 €/mês", PriceKind.MONTHLY),
    ("entrada 2.500 €", PriceKind.ENTRY),
    ("licitação inicial 1 €", PriceKind.AUCTION_START),
    ("lance atual 500 €", PriceKind.AUCTION_CURRENT),
]
_NON_RETAIL_MATRIX = [
    (raw, context, kind)
    for raw, kind in _NON_RETAIL_CASES
    for context in _SAFE_CONTEXTS[:12]
]


@pytest.mark.parametrize("raw,context,expected_kind", _NON_RETAIL_MATRIX)
def test_non_retail_matrix_never_becomes_retail(raw, context, expected_kind):
    result = parse_price_evidence(raw, context=context)

    assert result.kind is expected_kind
    assert result.value is not None
    assert result.rejection_reason


_SOURCE_LABELS = ["AUTOPT", "AUTOUNCLE", "OLX", "STANDVIRTUAL"]
_SOURCE_URLS = [
    "https://www.autouncle.pt/anuncio/1",
    "https://autouncle.pt/anuncio/2",
    "https://www.auto.pt/viatura/3",
    "https://auto.pt/viatura/4",
    "https://www.olx.pt/d/anuncio/5",
    "https://www.standvirtual.com/anuncio/6",
    "https://example.pt/anuncio/7",
    "https://www.autouncle.pt/stock/8",
    "https://www.auto.pt/stock/9",
    "https://www.olx.pt/item/10",
    "https://standvirtual.com/anuncio/11",
    "https://autouncle.pt/stock/12",
]
_SOURCE_MATRIX = [(label, url) for label in _SOURCE_LABELS for url in _SOURCE_URLS]


@pytest.mark.parametrize("label,url", _SOURCE_MATRIX)
def test_source_matrix_uses_hostname_as_authority(label, url):
    normalized = normalize_source(label, url)
    data = normalize_vehicle_data({"source": label, "url": url})

    if "autouncle.pt" in url:
        assert normalized == "AUTOUNCLE"
        assert data["source"] == "autouncle"
    elif "auto.pt" in url:
        assert normalized == "AUTOPT"
        assert data["source"] == "autopt"
    elif "olx.pt" in url:
        assert normalized == "OLX"
        assert data["source"] == "olx"
    elif "standvirtual.com" in url:
        assert normalized == "STANDVIRTUAL"
        assert data["source"] == "standvirtual"
    else:
        assert normalized in {"AUTOPT", "AUTOUNCLE", "OLX", "STANDVIRTUAL"}


def test_websocket_payload_serializes_enum_and_datetime_without_leaking_objects():
    from database.models import Source
    from datetime import datetime, timezone

    payload = vehicle_update_payload(SimpleNamespace(
        id=7,
        source=Source.OLX,
        source_id="abc",
        title="BMW 320d",
        brand="BMW",
        model="320d",
        year=2020,
        price=15_000.0,
        deal_score=None,
        estimated_value=None,
        last_seen=datetime(2026, 8, 13, tzinfo=timezone.utc),
    ))

    assert payload["source"] == "OLX"
    assert payload["last_seen"].endswith("+00:00")
    assert all(not hasattr(value, "value") for value in payload.values())
