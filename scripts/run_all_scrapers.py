"""
Execute all 4 lightweight scrapers and save results to autodeal.db.
"""
import sys
import asyncio
import logging
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_all")

from database.db import SessionLocal, init_db
from database.models import Vehicle, Source, VehicleType
from scrapers.piscapisca_lightweight import PiscaPiscaLightweight
from scrapers.carplus_lightweight import CarplusLightweightScraper
from scrapers.facebook_scraper import FacebookScraper
from scrapers.autoscout24_lightweight import AutoScout24Lightweight
from datetime import datetime, timezone

# --- Helpers ---

def _ensure_str(val):
    """Convert enum to string if needed."""
    if val is None:
        return ""
    if hasattr(val, 'value'):
        return str(val.value)
    return str(val)


def _lookup_source(source_str: str) -> Source:
    """Map any source string to Source enum."""
    mapping = {
        "piscapisca": Source.PISCAPISCA,
        "PISCAPISCA": Source.PISCAPISCA,
        "carplus": Source.CARPLUS,
        "CARPLUS": Source.CARPLUS,
        "facebook": Source.FACEBOOK,
        "FACEBOOK": Source.FACEBOOK,
        "autoscout24": Source.AUTOSCOUT24,
        "AUTOSCOUT24": Source.AUTOSCOUT24,
    }
    return mapping.get(source_str, Source.FACEBOOK)  # fallback


def save_listings(listings: list, source_name: str) -> tuple:
    """
    Save listings to database. Returns (added, skipped, errors).
    Each listing is a dict with keys: source, source_id, url, title, brand, model,
    price, year, km, fuel_type, transmission, horsepower, engine_size, location, images.
    """
    source_enum = _lookup_source(source_name)
    db = SessionLocal()
    added = 0
    skipped = 0
    errors = 0

    try:
        for listing in listings:
            try:
                raw_source = _ensure_str(listing.get("source", source_name))
                listing_source = _lookup_source(raw_source)
                source_id = str(listing.get("source_id", ""))
                url = str(listing.get("url", ""))
                title = str(listing.get("title", ""))
                brand = str(listing.get("brand", ""))
                model = str(listing.get("model", ""))
                price = listing.get("price")

                # Skip if missing required fields
                if not url or not title or price is None:
                    skipped += 1
                    continue

                try:
                    price = float(price)
                except (ValueError, TypeError):
                    skipped += 1
                    continue

                # Check if already exists (by source + source_id unique constraint)
                existing = db.query(Vehicle).filter(
                    Vehicle.source == listing_source,
                    Vehicle.source_id == source_id,
                ).first()

                if existing:
                    # Update last_seen
                    existing.last_seen = datetime.now(timezone.utc)
                    existing.price = price  # update price
                    existing.scrape_count = (existing.scrape_count or 0) + 1
                    skipped += 1
                    continue

                year = listing.get("year")
                if year is not None:
                    try:
                        year = int(year)
                    except (ValueError, TypeError):
                        year = None

                km = listing.get("km")
                if km is not None:
                    try:
                        km = int(km)
                    except (ValueError, TypeError):
                        km = None

                horsepower = listing.get("horsepower")
                if horsepower is not None:
                    try:
                        horsepower = int(horsepower)
                    except (ValueError, TypeError):
                        horsepower = None

                engine_size = listing.get("engine_size")
                if engine_size is not None:
                    try:
                        engine_size = int(engine_size)
                    except (ValueError, TypeError):
                        engine_size = None

                fuel_type = listing.get("fuel_type")
                transmission = listing.get("transmission")
                location = listing.get("location")
                images = listing.get("images", [])

                vehicle = Vehicle(
                    source=listing_source,
                    source_id=source_id,
                    url=url,
                    vehicle_type=VehicleType.carros,
                    brand=brand if brand else "Unknown",
                    model=model if model else "",
                    title=title,
                    price=price,
                    year=year,
                    km=km,
                    horsepower=horsepower,
                    engine_size=engine_size,
                    fuel_type=fuel_type,
                    transmission=transmission,
                    location=location,
                    images=images if images else None,
                    first_seen=datetime.now(timezone.utc),
                    last_seen=datetime.now(timezone.utc),
                )
                db.add(vehicle)
                added += 1

            except Exception as e:
                logger.warning(f"Error saving listing: {e}")
                errors += 1
                continue

        db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
    finally:
        db.close()

    return added, skipped, errors


def run_sync_scraper(scraper_instance, name, max_listings=100):
    """Run a synchronous scraper."""
    print(f"\n{'='*60}")
    print(f"  Running {name} (max_listings={max_listings})...")
    print(f"{'='*60}")
    try:
        listings = scraper_instance.scrape_listings(vehicle_type="carros", max_listings=max_listings)
        found = len(listings)
        print(f"  Found: {found} listings")
        added, skipped, errors = save_listings(listings, name)
        print(f"  Saved: {added} new, {skipped} skipped (existing/missing fields), {errors} errors")
        return found, added, skipped, errors
    except Exception as e:
        logger.error(f"  {name} failed: {e}", exc_info=True)
        return 0, 0, 0, 0


async def run_facebook_scraper(max_listings=100):
    """Run the async Facebook scraper."""
    name = "FACEBOOK"
    print(f"\n{'='*60}")
    print(f"  Running {name} (max_listings={max_listings})...")
    print(f"{'='*60}")
    try:
        scraper = FacebookScraper()
        listings = await scraper.scrape_listings(vehicle_type="carros", max_listings=max_listings)
        found = len(listings)
        print(f"  Found: {found} listings")
        added, skipped, errors = save_listings(listings, name)
        print(f"  Saved: {added} new, {skipped} skipped (existing/missing fields), {errors} errors")
        return found, added, skipped, errors
    except Exception as e:
        logger.error(f"  FACEBOOK failed: {e}", exc_info=True)
        return 0, 0, 0, 0


async def main():
    print("=" * 60)
    print("  AutoDeal Hunter — Run All Lightweight Scrapers")
    print("  Database: autodeal.db (SQLite)")
    print("=" * 60)

    # Initialize database
    print("\n[DB] Initializing database...")
    try:
        init_db()
        print("[DB] Database ready.")
    except Exception as e:
        logger.error(f"[DB] Init failed: {e}")
        print(f"[DB] Init failed: {e}")

    # Source name mapping
    SOURCE_NAMES = {
        "PiscaPisca": "piscapisca",
        "Carplus": "CARPLUS",
        "Facebook": "FACEBOOK",
        "AutoScout24": "autoscout24",
    }

    results = {}

    # 1. PiscaPisca (sync)
    scraper = PiscaPiscaLightweight()
    found, added, skipped, errors = run_sync_scraper(scraper, SOURCE_NAMES["PiscaPisca"], max_listings=100)
    results["PiscaPisca"] = (found, added, skipped, errors)

    # 2. Carplus (sync)
    scraper = CarplusLightweightScraper()
    found, added, skipped, errors = run_sync_scraper(scraper, SOURCE_NAMES["Carplus"], max_listings=100)
    results["Carplus"] = (found, added, skipped, errors)

    # 3. Facebook (async)
    found, added, skipped, errors = await run_facebook_scraper(max_listings=100)
    results["Facebook"] = (found, added, skipped, errors)

    # 4. AutoScout24 (sync)
    scraper = AutoScout24Lightweight()
    found, added, skipped, errors = run_sync_scraper(scraper, SOURCE_NAMES["AutoScout24"], max_listings=100)
    results["AutoScout24"] = (found, added, skipped, errors)

    # --- Summary ---
    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    total_found = 0
    total_added = 0
    total_skipped = 0
    total_errors = 0
    print(f"{'Scraper':<18} {'Found':>7} {'Saved':>7} {'Skipped':>7} {'Errors':>7}")
    print("-" * 48)
    for name in ["PiscaPisca", "Carplus", "Facebook", "AutoScout24"]:
        f, a, s, e = results.get(name, (0, 0, 0, 0))
        total_found += f
        total_added += a
        total_skipped += s
        total_errors += e
        print(f"{name:<18} {f:>7} {a:>7} {s:>7} {e:>7}")
    print("-" * 48)
    print(f"{'TOTAL':<18} {total_found:>7} {total_added:>7} {total_skipped:>7} {total_errors:>7}")
    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
