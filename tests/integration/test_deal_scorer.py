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
    
    assert result["score"] > 80
    assert result["is_good_deal"] is True
    assert result["market_avg"] == 21000.0
    
    bad_deal_v = Vehicle(
        brand="Golf", model="TDI", year=2020, price=25000.0, km=250000
    )
    result = scorer.score_vehicle(bad_deal_v)
    assert result["score"] < 40
    assert result["is_good_deal"] is False
