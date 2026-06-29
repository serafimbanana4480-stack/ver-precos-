"""
Investigate dashboard data issues
"""
from database.db import get_db_context
from database.models import Vehicle, ScrapingLog, Source
from sqlalchemy import func, desc

print("=" * 60)
print("DASHBOARD DATA INVESTIGATION")
print("=" * 60)

with get_db_context() as session:
    # 1. Total vs Active vehicles
    print("\n1. VEHICLE COUNTS")
    print("-" * 60)
    total = session.query(func.count(Vehicle.id)).scalar()
    active = session.query(func.count(Vehicle.id)).filter(Vehicle.is_active == True).scalar()
    inactive = session.query(func.count(Vehicle.id)).filter(Vehicle.is_active == False).scalar()
    
    print(f"Total vehicles: {total}")
    print(f"Active vehicles: {active}")
    print(f"Inactive vehicles: {inactive}")
    print(f"Discrepancy: {total - active if total != active else 0}")
    
    # 2. Vehicles by source
    print("\n2. VEHICLES BY SOURCE")
    print("-" * 60)
    for source in [Source.OLX, Source.STANDVIRTUAL, Source.AUTOSAPO]:
        count = session.query(func.count(Vehicle.id)).filter(Vehicle.source == source).scalar()
        print(f"{source.value}: {count}")
    
    # 3. ScrapingLog status
    print("\n3. SCRAPING LOG STATUS")
    print("-" * 60)
    for source_name in ["OLX", "Standvirtual", "AutoSapo"]:
        try:
            source_enum = Source[source_name.upper()]
            latest_log = session.query(ScrapingLog).filter(
                ScrapingLog.source == source_enum
            ).order_by(desc(ScrapingLog.finished_at)).first()
            
            if latest_log:
                print(f"{source_name}:")
                print(f"  Status: {latest_log.status}")
                print(f"  Listings found: {latest_log.listings_found or 0}")
                print(f"  Finished at: {latest_log.finished_at}")
                print(f"  Error message: {latest_log.error_message or 'None'}")
            else:
                print(f"{source_name}: No logs found")
        except Exception as e:
            print(f"{source_name}: Error - {e}")
    
    # 4. Sample vehicle data
    print("\n4. SAMPLE VEHICLE DATA (first 5)")
    print("-" * 60)
    vehicles = session.query(Vehicle).limit(5).all()
    for v in vehicles:
        print(f"\nID: {v.id}")
        print(f"  Source: {v.source.value if v.source else 'N/A'}")
        print(f"  Brand: {v.brand or 'N/A'}")
        print(f"  Model: {v.model or 'N/A'}")
        print(f"  Title: {v.title or 'N/A'}")
        print(f"  Price: {v.price}")
        print(f"  Year: {v.year}")
        print(f"  KM: {v.km}")
        print(f"  URL: {v.url or 'N/A'}")
        print(f"  Is Active: {v.is_active}")
        print(f"  Deal Score: {v.deal_score}")
        print(f"  Profit Potential: {v.profit_potential}")
    
    # 5. Data quality checks
    print("\n5. DATA QUALITY CHECKS")
    print("-" * 60)
    
    # Missing titles
    missing_titles = session.query(func.count(Vehicle.id)).filter(
        (Vehicle.title.is_(None)) | (Vehicle.title == '')
    ).scalar()
    print(f"Missing titles: {missing_titles}")
    
    # Missing URLs
    missing_urls = session.query(func.count(Vehicle.id)).filter(
        (Vehicle.url.is_(None)) | (Vehicle.url == '')
    ).scalar()
    print(f"Missing URLs: {missing_urls}")
    
    # Missing KM
    missing_km = session.query(func.count(Vehicle.id)).filter(Vehicle.km.is_(None)).scalar()
    print(f"Missing KM: {missing_km}")
    
    # Duplicate URLs
    from sqlalchemy import func
    duplicates = session.query(Vehicle.url, func.count(Vehicle.id)).group_by(
        Vehicle.url
    ).having(func.count(Vehicle.id) > 1).count()
    print(f"Duplicate URLs: {duplicates}")
    
    # Suspicious prices (too low or too high)
    too_low = session.query(func.count(Vehicle.id)).filter(Vehicle.price < 100).scalar()
    too_high = session.query(func.count(Vehicle.id)).filter(Vehicle.price > 1000000).scalar()
    print(f"Price < €100: {too_low}")
    print(f"Price > €1M: {too_high}")
    
    # 6. Deal score statistics
    print("\n6. DEAL SCORE STATISTICS")
    print("-" * 60)
    avg_score = session.query(func.avg(Vehicle.deal_score)).scalar()
    max_score = session.query(func.max(Vehicle.deal_score)).scalar()
    min_score = session.query(func.min(Vehicle.deal_score)).scalar()
    
    print(f"Average deal score: {f'{avg_score:.2f}' if avg_score is not None else 'N/A'}")
    print(f"Max deal score: {f'{max_score}' if max_score is not None else 'N/A'}")
    print(f"Min deal score: {f'{min_score}' if min_score is not None else 'N/A'}")
    
    # 7. Profit potential
    print("\n7. PROFIT POTENTIAL")
    print("-" * 60)
    total_profit = session.query(func.sum(Vehicle.profit_potential)).scalar()
    print(f"Total profit potential: €{f'{total_profit:.2f}' if total_profit is not None else '0'}")
    
    avg_profit = session.query(func.avg(Vehicle.profit_potential)).scalar()
    print(f"Average profit potential: €{f'{avg_profit:.2f}' if avg_profit is not None else '0'}")

print("\n" + "=" * 60)
print("INVESTIGATION COMPLETE")
print("=" * 60)
