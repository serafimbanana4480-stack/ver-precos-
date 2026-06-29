"""
Script to clean all data from database
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_context, engine
from database.models import Vehicle, ScrapingLog, PriceHistory, AIReview, Watchlist, Base
from sqlalchemy import text

def clean_database():
    """Delete all data from database tables"""
    print("=" * 80)
    print("DATABASE CLEANUP")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    with get_db_context() as db:
        # Count records before deletion
        vehicle_count = db.query(Vehicle).count()
        log_count = db.query(ScrapingLog).count()
        price_history_count = db.query(PriceHistory).count()
        ai_review_count = db.query(AIReview).count()
        watchlist_count = db.query(Watchlist).count()
        
        print(f"Records before cleanup:")
        print(f"  Vehicles: {vehicle_count}")
        print(f"  Scraping Logs: {log_count}")
        print(f"  Price History: {price_history_count}")
        print(f"  AI Reviews: {ai_review_count}")
        print(f"  Watchlist: {watchlist_count}")
        print()
        
        # Delete in order of dependencies
        print("Deleting data...")
        
        # Delete AI Reviews (depends on Vehicle)
        db.query(AIReview).delete()
        print("  ✅ AI Reviews deleted")
        
        # Delete Price History (depends on Vehicle)
        db.query(PriceHistory).delete()
        print("  ✅ Price History deleted")
        
        # Delete Watchlist (no dependencies)
        db.query(Watchlist).delete()
        print("  ✅ Watchlist deleted")
        
        # Delete Scraping Logs (no dependencies)
        db.query(ScrapingLog).delete()
        print("  ✅ Scraping Logs deleted")
        
        # Delete Vehicles (no dependencies after cascade deletes)
        db.query(Vehicle).delete()
        print("  ✅ Vehicles deleted")
        
        db.commit()
        
        # Verify cleanup
        vehicle_count_after = db.query(Vehicle).count()
        log_count_after = db.query(ScrapingLog).count()
        price_history_count_after = db.query(PriceHistory).count()
        ai_review_count_after = db.query(AIReview).count()
        watchlist_count_after = db.query(Watchlist).count()
        
        print(f"\nRecords after cleanup:")
        print(f"  Vehicles: {vehicle_count_after}")
        print(f"  Scraping Logs: {log_count_after}")
        print(f"  Price History: {price_history_count_after}")
        print(f"  AI Reviews: {ai_review_count_after}")
        print(f"  Watchlist: {watchlist_count_after}")
        
        if all(count == 0 for count in [vehicle_count_after, log_count_after, price_history_count_after, ai_review_count_after, watchlist_count_after]):
            print("\n✅ Database cleaned successfully!")
        else:
            print("\n⚠️ Warning: Some records may remain")
    
    print("\n" + "=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    from datetime import datetime
    clean_database()
