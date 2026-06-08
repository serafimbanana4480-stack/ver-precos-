"""
Database-based Search Service for AutoDeal IA Hunter
Queries SQLite/PostgreSQL directly — no Elasticsearch dependency required for basic search.
"""
from __future__ import annotations
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import and_, or_, desc
from database.db import get_db_context
from database.models import Vehicle, VehicleType, FuelType, Source

logger = logging.getLogger(__name__)


class SearchService:
    """Search vehicles using database queries with optional fuzzy matching"""

    def search(
        self,
        brand: Optional[str] = None,
        model: Optional[str] = None,
        vehicle_type: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        max_km: Optional[int] = None,
        min_km: Optional[int] = None,
        fuel_type: Optional[str] = None,
        location: Optional[str] = None,
        district: Optional[str] = None,
        source: Optional[str] = None,
        min_deal_score: Optional[float] = None,
        sort_by: str = "deal_score",
        sort_desc: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Search for vehicles with multiple filter criteria.

        Args:
            brand: Brand name (partial match supported)
            model: Model name (partial match supported)
            vehicle_type: "carros" or "motos"
            min_price: Minimum price in EUR
            max_price: Maximum price in EUR
            min_year: Minimum year
            max_year: Maximum year
            max_km: Maximum kilometers
            min_km: Minimum kilometers
            fuel_type: Fuel type filter
            location: Location (partial match)
            district: District filter
            source: Source filter (OLX, STANDVIRTUAL, etc.)
            min_deal_score: Minimum deal score (0-10)
            sort_by: Field to sort by
            sort_desc: Sort descending
            limit: Max results
            offset: Pagination offset

        Returns:
            List of vehicle dictionaries
        """
        conditions = [Vehicle.is_active == True]  # noqa: E712

        if brand:
            conditions.append(Vehicle.brand.ilike(f"%{brand}%"))
        if model:
            conditions.append(Vehicle.model.ilike(f"%{model}%"))
        if vehicle_type:
            try:
                vt = VehicleType(vehicle_type)
                conditions.append(Vehicle.vehicle_type == vt)
            except ValueError:
                logger.warning(f"Invalid vehicle_type: {vehicle_type}")
        if min_price is not None:
            conditions.append(Vehicle.price >= min_price)
        if max_price is not None:
            conditions.append(Vehicle.price <= max_price)
        if min_year is not None:
            conditions.append(Vehicle.year >= min_year)
        if max_year is not None:
            conditions.append(Vehicle.year <= max_year)
        if max_km is not None:
            conditions.append(Vehicle.km <= max_km)
        if min_km is not None:
            conditions.append(Vehicle.km >= min_km)
        if fuel_type:
            try:
                ft = FuelType(fuel_type.lower())
                conditions.append(Vehicle.fuel_type == ft)
            except ValueError:
                conditions.append(Vehicle.fuel_type.ilike(f"%{fuel_type}%"))
        if location:
            conditions.append(Vehicle.location.ilike(f"%{location}%"))
        if district:
            conditions.append(Vehicle.district.ilike(f"%{district}%"))
        if source:
            from utils.source_normalize import normalize_source
            norm = normalize_source(source)
            try:
                conditions.append(Vehicle.source == Source(norm))
            except ValueError:
                conditions.append(Vehicle.source.ilike(f"%{norm}%"))
        if min_deal_score is not None:
            conditions.append(Vehicle.deal_score >= min_deal_score)

        # Build sort column
        sort_map = {
            "price": Vehicle.price,
            "year": Vehicle.year,
            "km": Vehicle.km,
            "deal_score": Vehicle.deal_score,
            "profit_potential": Vehicle.profit_potential,
            "first_seen": Vehicle.first_seen,
        }
        sort_col = sort_map.get(sort_by, Vehicle.deal_score)

        with get_db_context() as db:
            query = db.query(Vehicle).filter(and_(*conditions))

            if sort_desc:
                query = query.order_by(desc(sort_col))
            else:
                query = query.order_by(sort_col)

            total = query.count()
            vehicles = query.offset(offset).limit(limit).all()

            results = []
            for v in vehicles:
                results.append({
                    "id": v.id,
                    "source": v.source.value if v.source else None,
                    "url": v.url,
                    "vehicle_type": v.vehicle_type.value if v.vehicle_type else None,
                    "brand": v.brand,
                    "model": v.model,
                    "version": v.version,
                    "year": v.year,
                    "km": v.km,
                    "horsepower": v.horsepower,
                    "engine_size": v.engine_size,
                    "fuel_type": v.fuel_type.value if v.fuel_type else None,
                    "transmission": v.transmission.value if v.transmission else None,
                    "location": v.location,
                    "district": v.district,
                    "price": v.price,
                    "estimated_value": v.estimated_value,
                    "deal_score": v.deal_score,
                    "profit_potential": v.profit_potential,
                    "profit_percentage": v.profit_percentage,
                    "title": v.title,
                    "image_count": v.image_count,
                    "condition_score": v.condition_score,
                    "ai_approved": v.ai_approved,
                    "ai_recommendation": v.ai_recommendation,
                    "first_seen": v.first_seen.isoformat() if v.first_seen else None,
                    "seller_name": v.seller_name,
                    "seller_type": v.seller_type,
                    "deal_grade": v.deal_grade,
                })

            logger.info(f"Search returned {len(results)} results (total: {total})")
            return results

    def quick_search(self, query: str, vehicle_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Quick search across brand, model, and title fields.

        Args:
            query: Free-text search query
            vehicle_type: Optional vehicle type filter
            limit: Max results
        """
        with get_db_context() as db:
            base = db.query(Vehicle).filter(Vehicle.is_active == True)  # noqa: E712

            if vehicle_type:
                try:
                    vt = VehicleType(vehicle_type)
                    base = base.filter(Vehicle.vehicle_type == vt)
                except ValueError:
                    pass

            # Search across brand, model, title, version
            like_pattern = f"%{query}%"
            results = base.filter(
                or_(
                    Vehicle.brand.ilike(like_pattern),
                    Vehicle.model.ilike(like_pattern),
                    Vehicle.title.ilike(like_pattern),
                    Vehicle.version.ilike(like_pattern),
                )
            ).order_by(desc(Vehicle.deal_score)).limit(limit).all()

            return [
                {
                    "id": v.id,
                    "brand": v.brand,
                    "model": v.model,
                    "year": v.year,
                    "price": v.price,
                    "estimated_value": v.estimated_value,
                    "deal_score": v.deal_score,
                    "profit_potential": v.profit_potential,
                    "profit_percentage": v.profit_percentage,
                    "km": v.km,
                    "fuel_type": v.fuel_type.value if v.fuel_type else None,
                    "location": v.location,
                    "source": v.source.value if v.source else None,
                    "url": v.url,
                    "vehicle_type": v.vehicle_type.value if v.vehicle_type else None,
                }
                for v in results
            ]

    def get_market_stats(
        self, brand: str, model: str, vehicle_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get market statistics for a specific brand/model."""
        from sqlalchemy import func

        with get_db_context() as db:
            base = db.query(Vehicle).filter(
                Vehicle.is_active == True,  # noqa: E712
                Vehicle.brand.ilike(f"%{brand}%"),
                Vehicle.model.ilike(f"%{model}%"),
            )
            if vehicle_type:
                try:
                    vt = VehicleType(vehicle_type)
                    base = base.filter(Vehicle.vehicle_type == vt)
                except ValueError:
                    pass

            total = base.count()
            if total == 0:
                return {"total": 0, "message": "No vehicles found"}

            avg_price = base.with_entities(func.avg(Vehicle.price)).scalar() or 0
            min_price = base.with_entities(func.min(Vehicle.price)).scalar() or 0
            max_price = base.with_entities(func.max(Vehicle.price)).scalar() or 0
            avg_year = base.with_entities(func.avg(Vehicle.year)).scalar() or 0
            avg_km = base.with_entities(func.avg(Vehicle.km)).scalar() or 0
            avg_deal_score = base.with_entities(func.avg(Vehicle.deal_score)).scalar() or 0

            # Top deals
            top_deals = (
                base.filter(Vehicle.deal_score >= 7.0)
                .order_by(desc(Vehicle.profit_potential))
                .limit(5)
                .all()
            )

            return {
                "total": total,
                "avg_price": round(float(avg_price), 2),
                "min_price": round(float(min_price), 2),
                "max_price": round(float(max_price), 2),
                "avg_year": round(float(avg_year), 1),
                "avg_km": round(float(avg_km), 0),
                "avg_deal_score": round(float(avg_deal_score), 2),
                "top_deals": [
                    {
                        "id": v.id,
                        "price": v.price,
                        "deal_score": v.deal_score,
                        "profit_potential": v.profit_potential,
                        "url": v.url,
                        "year": v.year,
                        "km": v.km,
                    }
                    for v in top_deals
                ],
            }