"""
Unit tests for DealFinder logic — specifically the calculate_combined_score
method and get_deal_summary, which can be tested without a DB connection.
Uses mock Vehicle objects to isolate the scoring logic.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


def make_vehicle(**kwargs):
    """Helper to create a mock Vehicle object with default values."""
    v = MagicMock()
    v.id = kwargs.get("id", 1)
    v.brand = kwargs.get("brand", "Volkswagen")
    v.model = kwargs.get("model", "Golf")
    v.year = kwargs.get("year", 2020)
    v.km = kwargs.get("km", 50000)
    v.price = kwargs.get("price", 15000.0)
    v.estimated_value = kwargs.get("estimated_value", 18000.0)
    v.deal_score = kwargs.get("deal_score", 7.5)
    v.profit_potential = kwargs.get("profit_potential", 3000.0)
    v.profit_percentage = kwargs.get("profit_percentage", 20.0)
    v.condition_score = kwargs.get("condition_score", None)
    v.ai_approved = kwargs.get("ai_approved", True)
    v.ai_confidence = kwargs.get("ai_confidence", None)
    v.url = kwargs.get("url", "https://example.com/car/1")
    v.source = kwargs.get("source", "olx")
    v.location = kwargs.get("location", "Lisboa")
    v.ai_review = kwargs.get("ai_review", None)
    v.images = kwargs.get("images", [])
    v.first_seen = kwargs.get("first_seen", datetime.now(timezone.utc))
    v.is_active = kwargs.get("is_active", True)
    # to_dict() returns a basic dict
    v.to_dict.return_value = {
        "id": v.id,
        "brand": v.brand,
        "model": v.model,
        "year": v.year,
        "km": v.km,
        "price": v.price,
        "estimated_value": v.estimated_value,
        "deal_score": v.deal_score,
        "profit_potential": v.profit_potential,
        "profit_percentage": v.profit_percentage,
        "url": v.url,
        "source": v.source,
        "location": v.location,
        "ai_approved": v.ai_approved,
        "ai_review": v.ai_review,
        "condition_score": v.condition_score,
    }
    return v


# ---------------------------------------------------------------------------
# DealFinder.calculate_combined_score Tests
# ---------------------------------------------------------------------------

class TestCalculateCombinedScore:
    """Test DealFinder.calculate_combined_score method"""

    @pytest.fixture
    def deal_finder(self):
        """Create DealFinder with mocked dependencies"""
        with patch("ai_agent.deal_finder.LLMReviewer"), \
             patch("ai_agent.deal_finder.VisionAnalyzer"):
            from ai_agent.deal_finder import DealFinder
            return DealFinder()

    def test_score_with_no_modifiers(self, deal_finder):
        """Base deal_score returned when no condition/confidence modifiers"""
        vehicle = make_vehicle(deal_score=7.0, condition_score=None,
                               ai_approved=True, ai_confidence=None)
        score = deal_finder.calculate_combined_score(vehicle)
        assert score == pytest.approx(7.0, abs=0.01)

    def test_score_capped_at_ten(self, deal_finder):
        """Score should never exceed 10.0"""
        vehicle = make_vehicle(deal_score=10.0, condition_score=10.0,
                               ai_approved=True, ai_confidence=1.0)
        score = deal_finder.calculate_combined_score(vehicle)
        assert score <= 10.0

    def test_score_floored_at_zero(self, deal_finder):
        """Score should never go below 0.0"""
        vehicle = make_vehicle(deal_score=1.0, condition_score=0.0,
                               ai_approved=False, ai_confidence=0.1)
        score = deal_finder.calculate_combined_score(vehicle)
        assert score >= 0.0

    def test_ai_rejection_penalizes_score(self, deal_finder):
        """ai_approved=False should halve the base score"""
        vehicle_approved = make_vehicle(deal_score=8.0, ai_approved=True,
                                        condition_score=None, ai_confidence=None)
        vehicle_rejected = make_vehicle(deal_score=8.0, ai_approved=False,
                                        condition_score=None, ai_confidence=None)
        score_approved = deal_finder.calculate_combined_score(vehicle_approved)
        score_rejected = deal_finder.calculate_combined_score(vehicle_rejected)
        assert score_rejected < score_approved
        assert score_rejected == pytest.approx(score_approved * 0.5, abs=0.01)

    def test_condition_score_blends_with_base(self, deal_finder):
        """condition_score 30% weight blended with deal_score 70%"""
        vehicle = make_vehicle(deal_score=8.0, condition_score=4.0,
                               ai_approved=True, ai_confidence=None)
        # Expected: 8.0 * 0.7 + 4.0 * 0.3 = 5.6 + 1.2 = 6.8
        score = deal_finder.calculate_combined_score(vehicle)
        assert score == pytest.approx(6.8, abs=0.05)

    def test_high_confidence_boosts_score(self, deal_finder):
        """ai_confidence=1.0 → confidence_factor=1.0 (no change)"""
        vehicle = make_vehicle(deal_score=6.0, condition_score=None,
                               ai_approved=True, ai_confidence=1.0)
        score = deal_finder.calculate_combined_score(vehicle)
        # confidence_factor = 0.5 + (1.0 * 0.5) = 1.0, no change
        assert score == pytest.approx(6.0, abs=0.01)

    def test_low_confidence_reduces_score(self, deal_finder):
        """ai_confidence=0.1 → confidence_factor=0.55, reduces score below base"""
        vehicle = make_vehicle(deal_score=8.0, condition_score=None,
                               ai_approved=True, ai_confidence=0.1)
        score = deal_finder.calculate_combined_score(vehicle)
        # confidence_factor = 0.5 + (0.1 * 0.5) = 0.55
        # score = 8.0 * 0.55 = 4.4
        assert score == pytest.approx(4.4, abs=0.01)
        # Crucially: it should be less than base score without confidence modifier
        vehicle_no_conf = make_vehicle(deal_score=8.0, condition_score=None,
                                       ai_approved=True, ai_confidence=None)
        base_score = deal_finder.calculate_combined_score(vehicle_no_conf)
        assert score < base_score


    def test_none_deal_score_defaults_to_five(self, deal_finder):
        """None deal_score should default to base score of 5.0"""
        vehicle = make_vehicle(deal_score=None, condition_score=None,
                               ai_approved=True, ai_confidence=None)
        score = deal_finder.calculate_combined_score(vehicle)
        assert score == pytest.approx(5.0, abs=0.01)

    def test_score_type_is_float(self, deal_finder):
        vehicle = make_vehicle(deal_score=7.5)
        score = deal_finder.calculate_combined_score(vehicle)
        assert isinstance(score, float)


# ---------------------------------------------------------------------------
# DealFinder.get_deal_summary Tests
# ---------------------------------------------------------------------------

class TestGetDealSummary:
    """Test DealFinder.get_deal_summary method"""

    @pytest.fixture
    def deal_finder(self):
        with patch("ai_agent.deal_finder.LLMReviewer"), \
             patch("ai_agent.deal_finder.VisionAnalyzer"):
            from ai_agent.deal_finder import DealFinder
            return DealFinder()

    def test_returns_dict(self, deal_finder):
        vehicle = make_vehicle()
        result = deal_finder.get_deal_summary(vehicle)
        assert isinstance(result, dict)

    def test_contains_key_fields(self, deal_finder):
        vehicle = make_vehicle(brand="Honda", model="Civic", year=2019,
                               price=12000.0, deal_score=6.5)
        result = deal_finder.get_deal_summary(vehicle)
        assert result["brand"] == "Honda"
        assert result["model"] == "Civic"
        assert result["year"] == 2019
        assert result["price"] == 12000.0
        assert result["deal_score"] == 6.5

    def test_ai_review_truncated_to_500(self, deal_finder):
        long_review = "A" * 1000
        vehicle = make_vehicle(ai_review=long_review)
        vehicle.to_dict.return_value = {
            "id": 1, "brand": "Test", "model": "Car",
            "ai_review": long_review,
        }
        result = deal_finder.get_deal_summary(vehicle)
        if result.get("ai_review"):
            assert len(result["ai_review"]) <= 500

    def test_handles_to_dict_exception_gracefully(self, deal_finder):
        vehicle = MagicMock()
        vehicle.to_dict.side_effect = Exception("DB session closed")
        result = deal_finder.get_deal_summary(vehicle)
        # Should return fallback dict
        assert isinstance(result, dict)
        assert result["brand"] == "Unknown"
        assert result["id"] is None

    def test_none_ai_review_stays_none(self, deal_finder):
        vehicle = make_vehicle(ai_review=None)
        result = deal_finder.get_deal_summary(vehicle)
        assert result.get("ai_review") is None


# ---------------------------------------------------------------------------
# DealFinder.export_deals_report Tests
# ---------------------------------------------------------------------------

class TestExportDealsReport:
    """Test DealFinder.export_deals_report method"""

    @pytest.fixture
    def deal_finder(self):
        with patch("ai_agent.deal_finder.LLMReviewer"), \
             patch("ai_agent.deal_finder.VisionAnalyzer"):
            from ai_agent.deal_finder import DealFinder
            return DealFinder()

    def test_export_as_dict_list(self, deal_finder):
        vehicles = [make_vehicle(brand="VW", price=15000.0),
                    make_vehicle(brand="BMW", price=25000.0)]
        result = deal_finder.export_deals_report(vehicles, format="dict")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_export_as_json_string(self, deal_finder):
        import json
        vehicles = [make_vehicle(brand="VW", price=15000.0)]
        result = deal_finder.export_deals_report(vehicles, format="json")
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_export_empty_list(self, deal_finder):
        result = deal_finder.export_deals_report([], format="dict")
        assert result == []

    def test_export_json_empty_list(self, deal_finder):
        import json
        result = deal_finder.export_deals_report([], format="json")
        assert json.loads(result) == []
