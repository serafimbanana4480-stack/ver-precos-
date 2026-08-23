import asyncio

from scripts.audit_scrapers import ScraperSpec, _price_check, run_spec, validate_rows


def _spec(source="OLX", website="https://www.olx.pt"):
    async def adapter(_vehicle_type, _max_listings):
        return []

    return ScraperSpec("test", source, website, adapter)


def test_audit_price_does_not_join_model_digits_to_price():
    row = {
        "title": "Peugeot 5008 22.580 €",
        "price": 22_580,
        "price_raw": "22.580 €",
    }
    price = _price_check(row, "OLX")
    assert price["valid_total_eur"] is True
    assert price["mismatch"] is False
    assert price["suspicious_range"] is False


def test_audit_flags_cross_source_fallback_url():
    result = validate_rows(
        [{
            "source": "FACEBOOK",
            "source_id": "x",
            "url": "https://www.olx.pt/d/anuncio/carro-x",
            "title": "Renault Clio",
            "price": 10_000,
            "vehicle_type": "carros",
        }],
        _spec("FACEBOOK", "https://www.facebook.com/marketplace"),
        "carros",
    )
    assert result["issues"]["cross_source_url"] == 1


def test_audit_does_not_call_rows_healthy_when_core_fields_are_missing():
    async def adapter(_vehicle_type, _max_listings):
        return [{
            "source": "OLX",
            "source_id": "x",
            "url": "https://www.olx.pt/d/anuncio/carro-x",
            "title": "Volkswagen Golf",
            "brand": "Volkswagen",
            "model": "Golf",
            "price": 10_000,
            "price_raw": "10.000 €",
            "currency": "EUR",
            "price_kind": "total",
            "vehicle_type": "carros",
        }]

    result = asyncio.run(
        run_spec(
            ScraperSpec("test", "OLX", "https://www.olx.pt", adapter),
            "carros",
            1,
            5,
        )
    )

    assert result["status"] == "degraded"
    assert result["field_missing"]["year"] == 1
