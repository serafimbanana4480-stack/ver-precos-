"""
Test data factories using factory-boy
"""
import factory
from datetime import datetime, timezone, timedelta
from database.models import Vehicle, PriceHistory, AIReview, ScrapingLog, Source, VehicleType, FuelType, Transmission


class VehicleFactory(factory.Factory):
    """Factory for Vehicle model"""
    class Meta:
        model = Vehicle
    
    source = Source.STANDVIRTUAL
    source_id = factory.Faker('uuid4')
    url = factory.Faker('url')
    vehicle_type = VehicleType.CAR
    brand = factory.Iterator(['Volkswagen', 'Renault', 'Peugeot', 'Citroen', 'Ford', 'Toyota'])
    model = factory.Faker('word')
    version = factory.Faker('word')
    year = factory.Faker('year')
    km = factory.Faker('random_int', min=0, max=300000)
    horsepower = factory.Faker('random_int', min=50, max=300)
    engine_size = factory.Faker('random_int', min=1000, max=5000)
    fuel_type = FuelType.GASOLINE
    transmission = Transmission.MANUAL
    doors = factory.Faker('random_int', min=2, max=5)
    seats = factory.Faker('random_int', min=2, max=7)
    color = factory.Faker('color_name')
    location = factory.Faker('city')
    district = factory.Faker('state')
    price = factory.Faker('random_int', min=1000, max=100000)
    estimated_value = factory.Faker('random_int', min=1000, max=100000)
    deal_score = factory.Faker('random_float', min=0, max=10)
    profit_potential = factory.Faker('random_int', min=0, max=5000)
    profit_percentage = factory.Faker('random_float', min=0, max=30)
    title = factory.Faker('sentence')
    description = factory.Faker('paragraph')
    images = factory.List([factory.Faker('url') for _ in range(3)])
    image_count = 3
    condition_score = factory.Faker('random_int', min=0, max=10)
    damages_detected = []
    has_accident = False
    ai_review = factory.Faker('paragraph')
    ai_approved = True
    ai_confidence = factory.Faker('random_float', min=0, max=1)
    ai_review_date = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    first_seen = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    last_seen = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    is_active = True


class PriceHistoryFactory(factory.Factory):
    """Factory for PriceHistory model"""
    class Meta:
        model = PriceHistory
    
    vehicle = factory.SubFactory(VehicleFactory)
    price = factory.Faker('random_int', min=1000, max=100000)
    recorded_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class AIReviewFactory(factory.Factory):
    """Factory for AIReview model"""
    class Meta:
        model = AIReview
    
    vehicle = factory.SubFactory(VehicleFactory)
    recommendation = factory.Iterator(['Approved', 'Rejected', 'Neutral'])
    confidence = factory.Faker('random_float', min=0, max=1)
    issues = factory.List([factory.Faker('word') for _ in range(3)])
    review_date = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class ScrapingLogFactory(factory.Factory):
    """Factory for ScrapingLog model"""
    class Meta:
        model = ScrapingLog
    
    source = Source.STANDVIRTUAL
    status = factory.Iterator(['running', 'completed', 'failed'])
    listings_found = factory.Faker('random_int', min=0, max=100)
    listings_added = factory.Faker('random_int', min=0, max=100)
    started_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    finished_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) + timedelta(minutes=10))
