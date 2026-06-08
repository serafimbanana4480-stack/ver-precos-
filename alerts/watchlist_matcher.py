"""
Watchlist Matcher — automatically matches new listings against watchlist criteria.
"""
from __future__ import annotations
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import and_

from database.db import get_db_context
from database.models import Watchlist, Vehicle, VehicleType

logger = logging.getLogger(__name__)


class WatchlistMatcher:
    """Automatically match new listings against watchlist criteria."""

    def check_all_watchlists(self) -> List[Dict[str, Any]]:
        """
        Check all active watchlists against active listings.
        Returns list of matches: [{watchlist, vehicle}, ...]
        """
        matches = []

        with get_db_context() as db:
            watchlists = db.query(Watchlist).filter(Watchlist.is_active == True).all()  # noqa: E712

            if not watchlists:
                logger.info("No active watchlists found")
                return []

            for wl in watchlists:
                wl_matches = self._match_watchlist(db, wl)
                matches.extend(wl_matches)

            # Update last_notified for matched watchlists
            now = datetime.now(timezone.utc)
            for match in matches:
                wl_id = match["watchlist"]["id"]
                db.query(Watchlist).filter(Watchlist.id == wl_id).update(
                    {"last_notified": now}
                )
                db.commit()

        logger.info(f"Watchlist check complete: {len(matches)} matches found")
        return matches

    def check_single_watchlist(self, watchlist_id: int) -> List[Dict[str, Any]]:
        """Check a single watchlist for matches."""
        with get_db_context() as db:
            wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
            if not wl:
                logger.warning(f"Watchlist {watchlist_id} not found")
                return []
            return self._match_watchlist(db, wl)

    def _match_watchlist(self, db, wl: Watchlist) -> List[Dict[str, Any]]:
        """Build query from watchlist criteria and find matching vehicles."""
        conditions = [Vehicle.is_active == True]  # noqa: E712

        if wl.brand:
            conditions.append(Vehicle.brand.ilike(f"%{wl.brand}%"))
        if wl.model:
            conditions.append(Vehicle.model.ilike(f"%{wl.model}%"))
        if wl.vehicle_type:
            conditions.append(Vehicle.vehicle_type == wl.vehicle_type)
        if wl.min_year is not None:
            conditions.append(Vehicle.year >= wl.min_year)
        if wl.max_year is not None:
            conditions.append(Vehicle.year <= wl.max_year)
        if wl.min_price is not None:
            conditions.append(Vehicle.price >= wl.min_price)
        if wl.max_price is not None:
            conditions.append(Vehicle.price <= wl.max_price)
        if wl.max_km is not None:
            conditions.append(Vehicle.km <= wl.max_km)
        if wl.min_profit is not None:
            conditions.append(Vehicle.profit_potential >= wl.min_profit)
        if wl.fuel_type:
            conditions.append(Vehicle.fuel_type == wl.fuel_type)

        vehicles = db.query(Vehicle).filter(and_(*conditions)).all()

        matches = []
        for v in vehicles:
            matches.append({
                "watchlist": {
                    "id": wl.id,
                    "name": wl.name,
                    "brand": wl.brand,
                    "model": wl.model,
                    "vehicle_type": wl.vehicle_type.value if wl.vehicle_type else None,
                },
                "vehicle": {
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
                    "fuel_type": v.fuel_type.value if v.fuel_type else None,
                    "location": v.location,
                    "source": v.source.value if v.source else None,
                    "url": v.url,
                    "title": v.title,
                    "vehicle_type": v.vehicle_type.value if v.vehicle_type else None,
                    "first_seen": v.first_seen.isoformat() if v.first_seen else None,
                },
            })

        if matches:
            logger.info(
                f"Watchlist '{wl.name}' matched {len(matches)} vehicles "
                f"(brand={wl.brand}, model={wl.model})"
            )

        return matches