from scripts.audit_scrapers import ScraperSpec, _price_check, validate_rows


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
