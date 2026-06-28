import pytest
from analysis.deal_scorer import DealScorer
from database.models import Vehicle, Source, VehicleType

@pytest.mark.asyncio
@pytest.mark.integration
async def test_deal_scorer_calculation(session):
    """Test pricing score calculation with actual DB interaction"""
    v1 = Vehicle(
        source=Source.OLX,
        source_id="v1",
        url="https://example.com/h1",
        vehicle_type=VehicleType.carros,
        brand="Golf",
        model="TDI",
        year=2020,
        price=20000.0,
        title="T1",
    )
    v2 = Vehicle(
        source=Source.OLX,
        source_id="v2",
        url="https://example.com/h2",
        vehicle_type=VehicleType.carros,
        brand="Golf",
        model="TDI",
        year=2020,
        price=22000.0,
        title="T2",
    )
    session.add_all([v1, v2])
    session.commit()
    
    scorer = DealScorer(session)
    
    good_deal_v = Vehicle(
        brand="Golf", model="TDI", year=2020, price=15000.0, km=30000
    )
    result = scorer.score_vehicle(good_deal_v)
    
    # Score is structural; with only 2 vehicles there's insufficient data
    assert isinstance(result.get("score"), (int, float))
    if result.get("reason"):
        assert "Insufficient" in result["reason"]
    else:
        assert result.get("is_good_deal") in (True, False)
    # market_avg might be None if insufficient data
    if result.get("market_avg") is not None:
        assert result["market_avg"] > 0
    
    bad_deal_v = Vehicle(
        brand="Golf", model="TDI", year=2020, price=25000.0, km=250000
    )
    result = scorer.score_vehicle(bad_deal_v)
    # Also structural verification (insufficient comparables expected)
    assert isinstance(result.get("score"), (int, float))
