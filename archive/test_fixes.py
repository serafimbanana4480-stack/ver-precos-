"""
Quick test to verify fixes for critical QA issues
"""
import asyncio
from scrapers.api_clients import fetch_olx_api
from processing.pipeline import production_pipeline

async def test_olx_description():
    """Test if OLX API now extracts descriptions"""
    print("Testing OLX API description extraction...")
    listings = await fetch_olx_api(vehicle_type='carros', limit=3)
    print(f"Listings fetched: {len(listings)}")
    
    for listing in listings:
        has_desc = bool(listing.get('description'))
        print(f"  {listing.get('source_id')}: Has description = {has_desc}")
        if has_desc:
            print(f"    Description preview: {listing.get('description')[:100]}...")
    
    return any(l.get('description') for l in listings)

def test_pipeline_persistence():
    """Test if pipeline persists data to database"""
    print("\nTesting pipeline data persistence...")
    
    import time
    unique_id = f"test_fix_{int(time.time())}"
    test_vehicle = {
        "source": "olx",
        "source_id": unique_id,
        "url": f"https://www.olx.pt/carro/test-{unique_id}",
        "title": "BMW 320i 2020 Test",
        "brand": "BMW",
        "model": "320i",
        "year": 2020,
        "km": 50000,
        "price": 15000.0,
        "vehicle_type": "carros",
        "description": "Test description for pipeline persistence verification",
        "images": ["https://via.placeholder.com/800x600"],
        "location": "Lisboa",
        "district": "Lisboa",
        "fuel_type": "Gasolina",
        "transmission": "Automático"
    }
    
    try:
        result = production_pipeline.process_vehicle(test_vehicle)
        print(f"Pipeline status: {result['status']}")
        
        if result['status'] == 'success':
            # Check if data persisted to database
            import sqlite3
            conn = sqlite3.connect("d:/VER PRECOS/autodeal.db")
            cursor = conn.cursor()
            cursor.execute("SELECT description, location FROM vehicles WHERE source_id = ?", (unique_id,))
            db_result = cursor.fetchone()
            conn.close()
            
            if db_result:
                print(f"Data persisted to database")
                print(f"  Description: {db_result[0][:50]}...")
                print(f"  Location: {db_result[1]}")
                return True
            else:
                print("Data NOT persisted to database")
                return False
        else:
            print(f"Pipeline failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"Pipeline test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("="*60)
    print("VERIFICATION TESTS FOR CRITICAL FIXES")
    print("="*60)
    
    # Test 1: OLX description extraction
    desc_test = await test_olx_description()
    
    # Test 2: Pipeline persistence
    persist_test = test_pipeline_persistence()
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"OLX Description Extraction: {'PASS' if desc_test else 'FAIL'}")
    print(f"Pipeline Data Persistence: {'PASS' if persist_test else 'FAIL'}")
    
    if desc_test and persist_test:
        print("\nCritical fixes verified successfully!")
        return 0
    else:
        print("\nSome fixes still need work")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
