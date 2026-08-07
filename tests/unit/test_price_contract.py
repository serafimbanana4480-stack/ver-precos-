import pytest

from processing.model_canon import extract_price_from_text
from scrapers.schema import PriceKind, VehicleListing, parse_price_evidence
from processing.quality import classify_listing



@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.500 €", 10_500.0),
        ("10 500 €", 10_500.0),
        ("10,500.00 €", 10_500.0),
        ("10.500,00 €", 10_500.0),
    ],
)
def test_parse_price_evidence_supports_pt_and_en_formats(raw, expected):
    result = parse_price_evidence(raw)

    assert result.value == expected
    assert result.currency == "EUR"
    assert result.kind is PriceKind.TOTAL
    assert result.raw == raw
    assert result.evidence
    assert result.rejection_reason is None


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("desde 199 €/mês", PriceKind.MONTHLY),
        ("entrada 2.500 €", PriceKind.ENTRY),
        ("licitação inicial 1 €", PriceKind.AUCTION_START),
    ],
)
def test_non_total_price_keeps_value_but_is_not_retail(raw, kind):
    result = parse_price_evidence(raw)

    assert result.value is not None
    assert result.kind is kind
    assert result.currency == "EUR"
    assert result.rejection_reason


def test_model_digits_are_not_a_price_candidate():
    result = parse_price_evidence("Peugeot 5008")

    assert result.value is None
    assert result.kind is PriceKind.UNKNOWN
    assert result.rejection_reason


@pytest.mark.parametrize("raw", ["500 €", "450.000 €"])
def test_legitimate_low_and_supercar_prices_are_preserved(raw):
    result = parse_price_evidence(raw)

    assert result.value in {500.0, 450_000.0}
    assert result.kind is PriceKind.TOTAL


def test_legacy_listing_preserves_rejected_price_evidence():
    raw = "desde 199 €/mês"

    listing = VehicleListing(title="Renault Clio", price=raw)

    assert listing.price is None
    assert listing.price_raw == raw
    assert listing.price_kind is PriceKind.MONTHLY
    assert listing.price_rejection_reason


def test_legacy_listing_does_not_parse_model_name_as_price():
    listing = VehicleListing(title="Peugeot 5008", price="Peugeot 5008")

    assert listing.price is None
    assert listing.price_raw == "Peugeot 5008"
    assert listing.price_kind is PriceKind.UNKNOWN
    assert listing.price_rejection_reason


def test_conflicting_supplied_provenance_is_overridden_and_recorded():
    listing = VehicleListing(
        title="BMW 320d",
        price="10.500 €",
        currency="USD",
        price_kind=PriceKind.MONTHLY,
    )

    assert listing.price == 10_500.0
    assert listing.currency == "EUR"
    assert listing.price_kind is PriceKind.TOTAL
    assert "proveniencia_moeda_inconsistente" in listing.price_rejection_reason
    assert "proveniencia_tipo_preco_inconsistente" in listing.price_rejection_reason
    assert (
        "proveniencia_tipo_preco_inconsistente"
        in listing.model_dump()["price_rejection_reason"]
    )

@pytest.mark.parametrize(
    ("raw", "expected"),
    [("500 €", 500.0), ("450.000 €", 450_000.0)],
)
def test_model_text_price_extraction_preserves_legitimate_extremes(raw, expected):
    value, cleaned = extract_price_from_text(f"Ferrari F8 {raw}")
    assert value == expected
    assert cleaned == "Ferrari F8"


def test_quality_rejects_non_total_price_from_explicit_provenance():
    result = classify_listing(
        {
            "title": "Renault Clio",
            "brand": "Renault",
            "model": "Clio",
            "price": 199.0,
            "currency": "EUR",
            "price_kind": PriceKind.MONTHLY,
        }
    )

    assert result["quality_status"] in {"quarantined", "invalid"}
    assert any("monthly" in reason or "mensal" in reason for reason in result["quality_reasons"])

@pytest.mark.parametrize(
    ("price_kind", "currency", "price", "reason"),
    [
        (PriceKind.ENTRY, "EUR", 2_500.0, "entry"),
        (PriceKind.AUCTION_START, "EUR", 1.0, "auction_start"),
        (PriceKind.AUCTION_CURRENT, "EUR", 1_000.0, "auction_current"),
        (PriceKind.TOTAL, "USD", 10_000.0, "moeda_nao_eur"),
    ],
)
def test_quality_rejects_non_retail_provenance_without_reference(
    price_kind, currency, price, reason
):
    result = classify_listing(
        {
            "title": "BMW 320d",
            "brand": "BMW",
            "model": "320d",
            "price": price,
            "currency": currency,
            "price_kind": price_kind,
            "year": 2020,
            "km": 50_000,
        }
    )

    assert result["quality_status"] in {"quarantined", "invalid"}
    assert any(reason in quality_reason for quality_reason in result["quality_reasons"])


def test_quality_marks_missing_year_and_km_for_review():
    result = classify_listing(
        {
            "title": "Renault Clio",
            "brand": "Renault",
            "model": "Clio",
            "price": 10_500.0,
            "currency": "EUR",
            "price_kind": PriceKind.TOTAL,
        }
    )

    assert result["quality_status"] == "quarantined"
    assert "ano_ausente" in result["quality_reasons"]
    assert "km_ausente" in result["quality_reasons"]


def test_quality_keeps_supported_supercar_price_eligible():
    result = classify_listing(
        {
            "title": "Ferrari F8",
            "brand": "Ferrari",
            "model": "F8",
            "price": 450_000.0,
            "currency": "EUR",
            "price_kind": PriceKind.TOTAL,
            "year": 2022,
            "km": 8_000,
        },
        reference_value=450_000.0,
    )

    assert result["quality_status"] == "valid_with_warning"
    assert any("400k" in reason for reason in result["quality_reasons"])
    
def test_quality_rejects_unknown_parser_provenance():
    result = classify_listing(
        {
            "title": "Peugeot 5008",
            "brand": "Peugeot",
            "model": "5008",
            "price": 10_500.0,
            "price_raw": "Peugeot 5008",
            "price_kind": PriceKind.UNKNOWN,
            "price_rejection_reason": "preco_sem_evidencia_monetaria",
            "year": 2020,
            "km": 80_000,
        }
    )

    assert result["quality_status"] == "quarantined"
    assert "preco_tipo_desconhecido" in result["quality_reasons"]
    assert "preco_sem_evidencia_monetaria" in result["quality_reasons"]

@pytest.mark.parametrize("raw", [None, "", "0 €", "-1 €", "sem preço"])
def test_impossible_or_absent_price_is_explained(raw):
    result = parse_price_evidence(raw)

    assert result.value is None or result.value <= 0
    assert result.rejection_reason


def test_non_eur_price_is_preserved_but_rejected_for_retail():
    result = parse_price_evidence("10,000 USD")

    assert result.value == 10_000.0
    assert result.currency == "USD"
    assert result.kind is PriceKind.TOTAL
    assert result.rejection_reason == "moeda_nao_eur"


@pytest.mark.parametrize("source", ["LEILOSOC", "AUTOLINE", "MARTELO"])
def test_auction_source_context_never_becomes_retail_total(source):
    result = parse_price_evidence("200 €", context=f"source={source}")

    assert result.value == 200.0
    assert result.kind is PriceKind.AUCTION_START
    assert result.rejection_reason
