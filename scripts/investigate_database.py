"""
Investigation script to check database status and identify issues
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_context
from database.models import Vehicle, ScrapingLog, PriceHistory, Source, VehicleType
from datetime import datetime, timezone, timedelta
import json

def investigate_database():
    """Comprehensive database investigation"""
    print("=" * 80)
    print("DATABASE INVESTIGATION REPORT")
    print("=" * 80)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
    
    with get_db_context() as db:
        # 1. Total vehicle counts
        print("1. VEHICLE COUNTS")
        print("-" * 80)
        total_vehicles = db.query(Vehicle).count()
        active_vehicles = db.query(Vehicle).filter(Vehicle.is_active == True).count()
        inactive_vehicles = db.query(Vehicle).filter(Vehicle.is_active == False).count()
        
        print(f"Total vehicles in database: {total_vehicles}")
        print(f"Active vehicles: {active_vehicles}")
        print(f"Inactive vehicles: {inactive_vehicles}")
        
        if total_vehicles > 0:
            print(f"\nActive ratio: {active_vehicles/total_vehicles*100:.1f}%")
        
        # 2. Vehicles by source
        print("\n2. VEHICLES BY SOURCE")
        print("-" * 80)
        for source in Source:
            count = db.query(Vehicle).filter(Vehicle.source == source).count()
            active_count = db.query(Vehicle).filter(Vehicle.source == source, Vehicle.is_active == True).count()
            print(f"{source.value}: {count} total, {active_count} active")
        
        # 3. ScrapingLog analysis
        print("\n3. SCRAPING LOG ANALYSIS")
        print("-" * 80)
        total_logs = db.query(ScrapingLog).count()
        print(f"Total scraping logs: {total_logs}")
        
        if total_logs > 0:
            for source in Source:
                logs = db.query(ScrapingLog).filter(ScrapingLog.source == source).order_by(ScrapingLog.started_at.desc()).limit(5).all()
                print(f"\n{source.value.upper()} - Last 5 logs:")
                for log in logs:
                    status_emoji = "✅" if log.status == "completed" else "❌" if log.status == "failed" else "⏳"
                    print(f"  {status_emoji} {log.started_at.strftime('%Y-%m-%d %H:%M:%S')} - {log.status}")
                    print(f"     Listings: found={log.listings_found}, added={log.listings_added}, updated={log.listings_updated}")
                    if log.error_message:
                        print(f"     Error: {log.error_message[:100]}...")
        else:
            print("No scraping logs found in database")
        
        # 4. Data quality checks
        print("\n4. DATA QUALITY CHECKS")
        print("-" * 80)
        
        # Check for missing critical fields
        missing_price = db.query(Vehicle).filter(Vehicle.price.is_(None)).count()
        missing_year = db.query(Vehicle).filter(Vehicle.year.is_(None)).count()
        missing_km = db.query(Vehicle).filter(Vehicle.km.is_(None)).count()
        missing_url = db.query(Vehicle).filter(Vehicle.url.is_(None)).count()
        
        print(f"Vehicles missing price: {missing_price}")
        print(f"Vehicles missing year: {missing_year}")
        print(f"Vehicles missing KM: {missing_km}")
        print(f"Vehicles missing URL: {missing_url}")
        
        # Check for deal scores
        with_deal_score = db.query(Vehicle).filter(Vehicle.deal_score.isnot(None)).count()
        without_deal_score = db.query(Vehicle).filter(Vehicle.deal_score.is_(None)).count()
        print(f"\nVehicles with deal score: {with_deal_score}")
        print(f"Vehicles without deal score: {without_deal_score}")
        
        # Check for profit potential
        with_profit = db.query(Vehicle).filter(Vehicle.profit_potential.isnot(None)).count()
        without_profit = db.query(Vehicle).filter(Vehicle.profit_potential.is_(None)).count()
        print(f"Vehicles with profit potential: {with_profit}")
        print(f"Vehicles without profit potential: {without_profit}")
        
        # 5. Metrics calculation
        print("\n5. CURRENT METRICS")
        print("-" * 80)
        if active_vehicles > 0:
            avg_deal_score = db.query(Vehicle.deal_score).filter(Vehicle.is_active == True, Vehicle.deal_score.isnot(None)).all()
            if avg_deal_score:
                scores = [s[0] for s in avg_deal_score]
                print(f"Average deal score: {sum(scores)/len(scores):.2f}/10")
            
            avg_price = db.query(Vehicle.price).filter(Vehicle.is_active == True).all()
            if avg_price:
                prices = [p[0] for p in avg_price]
                print(f"Average price: €{sum(prices)/len(prices):.2f}")
            
            total_profit = db.query(Vehicle.profit_potential).filter(Vehicle.is_active == True, Vehicle.profit_potential.isnot(None)).all()
            if total_profit:
                profits = [p[0] for p in total_profit]
                print(f"Total profit potential: €{sum(profits):.2f}")
        else:
            print("No active vehicles to calculate metrics")
        
        # 6. Data freshness
        print("\n6. DATA FRESHNESS")
        print("-" * 80)
        now = datetime.now(timezone.utc)
        
        for source in Source:
            # Get most recent vehicle from this source
            latest_vehicle = db.query(Vehicle).filter(
                Vehicle.source == source,
                Vehicle.is_active == True
            ).order_by(Vehicle.last_seen.desc()).first()
            
            if latest_vehicle:
                # Handle both naive and aware datetimes
                last_seen = latest_vehicle.last_seen
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                days_since = (now - last_seen).days
                print(f"{source.value}: Last seen {days_since} days ago ({last_seen.strftime('%Y-%m-%d %H:%M')})")
            else:
                print(f"{source.value}: No vehicles found")
        
        # 7. Duplicate check
        print("\n7. DUPLICATE CHECK")
        print("-" * 80)
        # Check for duplicate URLs
        from sqlalchemy import func
        duplicates = db.query(Vehicle.url, func.count(Vehicle.url)).group_by(Vehicle.url).having(func.count(Vehicle.url) > 1).all()
        if duplicates:
            print(f"Found {len(duplicates)} duplicate URLs:")
            for url, count in duplicates[:5]:
                print(f"  {url[:80]}... ({count} copies)")
        else:
            print("No duplicate URLs found")
        
        # 8. Price history
        print("\n8. PRICE HISTORY")
        print("-" * 80)
        price_history_count = db.query(PriceHistory).count()
        print(f"Total price history entries: {price_history_count}")
        
        if price_history_count > 0:
            latest_price = db.query(PriceHistory).order_by(PriceHistory.recorded_at.desc()).first()
            print(f"Latest price entry: {latest_price.recorded_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("\n" + "=" * 80)
        print("INVESTIGATION COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    investigate_database()
