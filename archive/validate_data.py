from database.db import get_db_context
from database.models import Vehicle
from sqlalchemy import func, or_

with get_db_context() as session:
    total = session.query(func.count(Vehicle.id)).scalar()
    print(f'Total vehicles: {total}')
    
    print(f'\nBy source:')
    for src in ['olx', 'standvirtual', 'autosapo']:
        count = session.query(func.count(Vehicle.id)).filter(Vehicle.source == src).scalar()
        print(f'  {src}: {count}')
    
    print(f'\nPrice validation:')
    null_prices = session.query(func.count(Vehicle.id)).filter(Vehicle.price.is_(None)).scalar()
    print(f'  Null prices: {null_prices}')
    
    # Check for unrealistic prices
    too_low = session.query(func.count(Vehicle.id)).filter(Vehicle.price < 100).scalar()
    too_high = session.query(func.count(Vehicle.id)).filter(Vehicle.price > 1000000).scalar()
    print(f'  Price < €100: {too_low}')
    print(f'  Price > €1M: {too_high}')
    
    print(f'\nURL validation:')
    null_urls = session.query(func.count(Vehicle.id)).filter(
        or_(Vehicle.url.is_(None), Vehicle.url == '')
    ).scalar()
    print(f'  Null/empty URLs: {null_urls}')
    
    print(f'\nYear validation:')
    null_years = session.query(func.count(Vehicle.id)).filter(Vehicle.year.is_(None)).scalar()
    invalid_years = session.query(func.count(Vehicle.id)).filter(
        or_(Vehicle.year < 1980, Vehicle.year > 2026)
    ).scalar()
    print(f'  Null years: {null_years}')
    print(f'  Invalid years (<1980 or >2026): {invalid_years}')
    
    print(f'\nKM validation:')
    null_km = session.query(func.count(Vehicle.id)).filter(Vehicle.km.is_(None)).scalar()
    invalid_km = session.query(func.count(Vehicle.id)).filter(Vehicle.km < 0).scalar()
    print(f'  Null KM: {null_km}')
    print(f'  Negative KM: {invalid_km}')
    
    print(f'\nSample data (first 5):')
    vehicles = session.query(Vehicle).limit(5).all()
    for v in vehicles:
        print(f'  {v.source}: {v.title[:50] if v.title else "N/A"} | Price: {v.price} | Year: {v.year} | KM: {v.km}')
