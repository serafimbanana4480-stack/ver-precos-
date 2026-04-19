import pytest
import json
from scrapers.ai_extractor import AIExtractor
from scrapers.schema import VehicleListing

@pytest.fixture
def extractor():
    return AIExtractor()

def test_parse_llm_response_with_json_block(extractor):
    raw_text = """
    Here is the data you requested:
    ```json
    [
      {
        "title": "BMW 320d",
        "price": "15.000 €",
        "km": "150.000 km",
        "year": "2015"
      }
    ]
    ```
    I hope this helps!
    """
    results = extractor._parse_llm_response(raw_text)
    assert len(results) == 1
    assert results[0]["title"] == "BMW 320d"
    assert results[0]["price"] == 15000.0
    assert results[0]["km"] == 150000
    assert results[0]["year"] == 2015

def test_parse_llm_response_raw_list(extractor):
    raw_text = '[{"title": "Audi A4", "price": 12000}]'
    results = extractor._parse_llm_response(raw_text)
    assert len(results) == 1
    assert results[0]["title"] == "Audi A4"
    assert results[0]["price"] == 12000.0

def test_parse_llm_response_single_object(extractor):
    raw_text = '{"title": "Mercedes C220", "price": "20.000"}'
    results = extractor._parse_llm_response(raw_text)
    assert len(results) == 1
    assert results[0]["title"] == "Mercedes C220"
    assert results[0]["price"] == 20000.0

def test_parse_llm_response_single_object_with_text(extractor):
    raw_text = """
    Found one car:
    ```json
    {
      "title": "Mercedes C220",
      "price": "20.000"
    }
    ```
    """
    results = extractor._parse_llm_response(raw_text)
    assert len(results) == 1
    assert results[0]["title"] == "Mercedes C220"
    assert results[0]["price"] == 20000.0

def test_parse_llm_response_invalid_json(extractor):
    raw_text = "This is not JSON at all."
    results = extractor._parse_llm_response(raw_text)
    assert results == []

def test_vehicle_listing_price_parsing():
    # Test Portuguese format (dot as thousands separator)
    assert VehicleListing(title="Test", price="10.500").price == 10500.0
    assert VehicleListing(title="Test", price="10.500,50").price == 10500.5
    
    # Test with multiple dots (thousands separators)
    assert VehicleListing(title="Test", price="1.250.000").price == 1250000.0

    # Test with comma as thousands separator (English style)
    # The current implementation assumes , is decimal if no dot is present.
    # "10,500" -> 10.5 in PT context.
    # "10,500.00" -> 10500.0
    assert VehicleListing(title="Test", price="10,500.00").price == 10500.0
    
    # Test with currency
    assert VehicleListing(title="Test", price="15.000 €").price == 15000.0
    assert VehicleListing(title="Test", price="EUR 15.000").price == 15000.0
    
    # Test clean numeric
    assert VehicleListing(title="Test", price=12000).price == 12000.0
    assert VehicleListing(title="Test", price=12000.5).price == 12000.5
    
    # Test messy strings
    assert VehicleListing(title="Test", price="  12 000  ").price == 12000.0
    assert VehicleListing(title="Test", price="Price: 15.000€ (Negotiable)").price == 15000.0

def test_vehicle_listing_km_parsing():
    assert VehicleListing(title="Test", km="120.000 km").km == 120000
    assert VehicleListing(title="Test", km="120 000").km == 120000
    assert VehicleListing(title="Test", km=150000).km == 150000
    assert VehicleListing(title="Test", km="100.000.000").km == 100000000
    assert VehicleListing(title="Test", km="100000kms").km == 100000

def test_parse_llm_response_validation_failure(extractor):
    # Missing title (required)
    raw_text = '[{"price": 10000}]'
    results = extractor._parse_llm_response(raw_text)
    assert results == []

    # Mixed valid and invalid
    raw_text = """
    [
      {"title": "Valid Car", "price": 10000},
      {"price": 5000}
    ]
    """
    results = extractor._parse_llm_response(raw_text)
    assert len(results) == 1
    assert results[0]["title"] == "Valid Car"

def test_vehicle_listing_year_parsing():
    assert VehicleListing(title="Test", year="2020").year == 2020
    assert VehicleListing(title="Test", year=2019).year == 2019
    assert VehicleListing(title="Test", year="Ano: 2018").year == 2018
    assert VehicleListing(title="Test", year="2017/05").year == 2017
    assert VehicleListing(title="Test", year="Mês: 05, Ano: 2016").year == 2016

def test_parse_llm_response_resilience(extractor):
    # Test with multiple JSON-like blocks, should pick the list one
    raw_text = """
    Some text before.
    {"not": "a list"}
    ```json
    [
      {"title": "Car 1", "price": "1000"},
      {"title": "Car 2", "price": "2000"}
    ]
    ```
    Some text after.
    """
    results = extractor._parse_llm_response(raw_text)
    assert len(results) == 2
    assert results[0]["title"] == "Car 1"
    assert results[1]["title"] == "Car 2"

def test_parse_llm_response_very_messy(extractor):
    raw_text = """
    Here is some garbage.
    
    [{"title": "Valid 1", "price": 100}]
    
    More garbage.
    
    ```json
    [
      {"title": "Valid 2", "price": 200},
      {"price": 300}
    ]
    ```
    
    Even more garbage.
    """
    results = extractor._parse_llm_response(raw_text)
    # It should pick the markdown block and then filter out the invalid item
    assert len(results) == 1
    assert results[0]["title"] == "Valid 2"

def test_vehicle_listing_int_fields_parsing():
    assert VehicleListing(title="Test", horsepower="150 cv").horsepower == 150
    assert VehicleListing(title="Test", engine_size="1995 cm3").engine_size == 1995
    assert VehicleListing(title="Test", doors="5 portas").doors == 5
    assert VehicleListing(title="Test", seats="5 lugares").seats == 5
    assert VehicleListing(title="Test", horsepower="N/A").horsepower is None
