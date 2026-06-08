"""
Comprehensive unit tests for scrapers/schema.py validators.
Tests the VehicleListing Pydantic model's field validators with real-world
Portuguese marketplace data formats.
"""
import pytest
from scrapers.schema import VehicleListing, ListingSchema, ScrapedVehicle


# ---------------------------------------------------------------------------
# Price Parser Tests
# ---------------------------------------------------------------------------

class TestPriceParser:
    """Test VehicleListing.parse_price field validator"""

    @pytest.mark.parametrize("raw, expected", [
        # Integers and floats passed directly
        (15000, 15000.0),
        (15000.0, 15000.0),
        (0, 0.0),
        # Portuguese thousands format: 10.500 → 10500
        ("10.500", 10500.0),
        ("25.000", 25000.0),
        ("150.000", 150000.0),
        # Portuguese full format: 10.500,00 → 10500.0
        ("10.500,00", 10500.0),
        ("25.990,50", 25990.5),
        # English thousands format: 10,500 → 10500
        ("10,500", 10500.0),
        # English decimal format: 10,500.00 → 10500.0
        ("10,500.00", 10500.0),
        # Simple string integer
        ("15000", 15000.0),
        # String with currency symbol
        ("€ 15.000", 15000.0),
        ("15.000 €", 15000.0),
        # String with spaces
        ("15 000", 15000.0),
        # None → None
        (None, None),
        # Empty string → None
        ("", None),
        # Junk → None
        ("N/A", None),
        ("Sob consulta", None),
    ])
    def test_price_parsing(self, raw, expected):
        listing = VehicleListing(title="Test", price=raw)
        assert listing.price == expected, f"price={raw!r} → expected {expected}, got {listing.price}"

    def test_price_zero_is_valid(self):
        listing = VehicleListing(title="Test", price=0)
        assert listing.price == 0.0

    def test_price_large_value(self):
        listing = VehicleListing(title="Test", price="350.000")
        assert listing.price == 350000.0


# ---------------------------------------------------------------------------
# KM Parser Tests
# ---------------------------------------------------------------------------

class TestKmParser:
    """Test VehicleListing.parse_km field validator"""

    @pytest.mark.parametrize("raw, expected", [
        (50000, 50000),
        (50000.7, 50000),
        ("50000", 50000),
        ("50.000", 50000),
        ("50.000 km", 50000),
        ("50 000 km", 50000),
        ("50,000", 50000),
        ("50,000 km", 50000),
        ("0", 0),
        (None, None),
        ("", None),
        ("N/A", None),
        ("Km desconhecido", None),
    ])
    def test_km_parsing(self, raw, expected):
        listing = VehicleListing(title="Test", km=raw)
        assert listing.km == expected, f"km={raw!r} → expected {expected}, got {listing.km}"

    def test_km_new_vehicle_zero(self):
        listing = VehicleListing(title="Test", km=0)
        assert listing.km == 0

    def test_km_high_mileage(self):
        listing = VehicleListing(title="Test", km="250.000 km")
        assert listing.km == 250000


# ---------------------------------------------------------------------------
# Year Parser Tests
# ---------------------------------------------------------------------------

class TestYearParser:
    """Test VehicleListing.parse_year field validator"""

    @pytest.mark.parametrize("raw, expected", [
        (2020, 2020),
        ("2020", 2020),
        ("2019", 2019),
        ("Reg. 2020", 2020),
        ("Ano: 2018", 2018),
        ("1998", 1998),
        ("2000", 2000),
        (None, None),
        ("", None),
        ("N/A", None),
        ("ano desconhecido", None),
    ])
    def test_year_parsing(self, raw, expected):
        listing = VehicleListing(title="Test", year=raw)
        assert listing.year == expected, f"year={raw!r} → expected {expected}, got {listing.year}"

    def test_year_at_boundary_1900(self):
        listing = VehicleListing(title="Test", year="1900")
        # 1900 matches the pattern \b(19|20)\d{2}\b
        assert listing.year == 1900

    def test_year_at_boundary_2099(self):
        listing = VehicleListing(title="Test", year="2099")
        assert listing.year == 2099


# ---------------------------------------------------------------------------
# Integer Field Parser Tests (horsepower, engine_size, doors, seats, etc.)
# ---------------------------------------------------------------------------

class TestIntFieldParser:
    """Test VehicleListing.parse_int_fields validator for multiple fields"""

    @pytest.mark.parametrize("field, raw, expected", [
        # horsepower
        ("horsepower", 150, 150),
        ("horsepower", 150.7, 150),
        ("horsepower", "150 cv", 150),
        ("horsepower", "150cv", 150),
        ("horsepower", None, None),
        ("horsepower", "", None),
        # engine_size (cc)
        ("engine_size", 1998, 1998),
        ("engine_size", "1998 cm3", 1998),
        ("engine_size", "1.998 cm3", 1998),
        ("engine_size", "2000cc", 2000),
        ("engine_size", None, None),
        # doors
        ("doors", 5, 5),
        ("doors", "5", 5),
        ("doors", "5 portas", 5),
        ("doors", None, None),
        # seats
        ("seats", 7, 7),
        ("seats", "7 lugares", 7),
        ("seats", None, None),
        # num_owners
        ("num_owners", 1, 1),
        ("num_owners", "2 proprietários", 2),
        ("num_owners", None, None),
        # warranty_months
        ("warranty_months", 24, 24),
        ("warranty_months", "12 meses", 12),
        ("warranty_months", None, None),
    ])
    def test_int_field_parsing(self, field, raw, expected):
        listing = VehicleListing(title="Test", **{field: raw})
        actual = getattr(listing, field)
        assert actual == expected, f"{field}={raw!r} → expected {expected}, got {actual}"


# ---------------------------------------------------------------------------
# VehicleListing Defaults and Optional Fields
# ---------------------------------------------------------------------------

class TestVehicleListingDefaults:
    """Test VehicleListing default values and optional fields"""

    def test_minimal_required_fields(self):
        """Only title is required"""
        listing = VehicleListing(title="Volkswagen Golf 2020")
        assert listing.title == "Volkswagen Golf 2020"
        assert listing.price is None
        assert listing.year is None
        assert listing.km is None
        assert listing.fuel_type is None
        assert listing.images == []
        assert listing.extras == []
        assert listing.aftermarket_mods == []

    def test_full_vehicle_listing(self):
        """Test a complete vehicle listing"""
        listing = VehicleListing(
            title="Volkswagen Golf 1.6 TDI",
            price="15.500",
            year=2018,
            km="85.000 km",
            fuel_type="diesel",
            transmission="manual",
            location="Lisboa",
            brand="Volkswagen",
            model="Golf",
            horsepower="115 cv",
            engine_size="1598 cm3",
            doors=5,
            seats=5,
            color="Cinzento",
            seller_name="Particular",
            seller_type="particular",
            is_national=True,
            num_owners=2,
            warranty_months=0,
        )
        assert listing.price == 15500.0
        assert listing.km == 85000
        assert listing.horsepower == 115
        assert listing.engine_size == 1598
        assert listing.is_national is True
        assert listing.num_owners == 2

    def test_motorcycle_specific_fields(self):
        """Test motorcycle-specific fields"""
        listing = VehicleListing(
            title="Yamaha MT-07 2021",
            price="8.500",
            engine_type="twin",
            riding_style="naked",
            has_abs=True,
            has_traction_control=False,
            seat_height=805,
            wet_weight=184,
            license_category="A",
            aftermarket_mods=["slip-on exhaust", "bar end mirrors"],
        )
        assert listing.engine_type == "twin"
        assert listing.riding_style == "naked"
        assert listing.has_abs is True
        assert listing.has_traction_control is False
        assert listing.seat_height == 805
        assert listing.wet_weight == 184
        assert listing.license_category == "A"
        assert len(listing.aftermarket_mods) == 2


# ---------------------------------------------------------------------------
# ListingSchema Backward Compatibility
# ---------------------------------------------------------------------------

class TestListingSchema:
    """Test ListingSchema (legacy compatibility wrapper)"""

    def test_title_defaults_to_empty(self):
        """ListingSchema allows empty title unlike VehicleListing"""
        schema = ListingSchema()
        assert schema.title == ""

    def test_scraped_vehicle_alias(self):
        """ScrapedVehicle is an alias for VehicleListing"""
        vehicle = ScrapedVehicle(title="Test")
        assert isinstance(vehicle, VehicleListing)

    def test_inherits_price_parsing(self):
        """ListingSchema inherits price parsing"""
        schema = ListingSchema(price="10.500,00")
        assert schema.price == 10500.0


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases and boundary conditions"""

    def test_price_with_only_comma_decimal(self):
        """'15,5' should be treated as 15.5"""
        listing = VehicleListing(title="Test", price="15,5")
        assert listing.price == 15.5

    def test_price_with_multiple_dots_thousands(self):
        """'1.000.000' → 1000000 (multiple dots = all thousands separators)"""
        listing = VehicleListing(title="Test", price="1.000.000")
        assert listing.price == 1000000.0

    def test_images_defaults_to_empty_list(self):
        listing = VehicleListing(title="Test")
        assert listing.images == []
        assert isinstance(listing.images, list)

    def test_source_id_optional(self):
        listing = VehicleListing(title="Test")
        assert listing.source_id is None

    def test_description_optional(self):
        listing = VehicleListing(title="Test", description="Great car, full service history.")
        assert listing.description == "Great car, full service history."
