"""
API Clients for external services
OLX, Standvirtual, AutoSapo APIs
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from config import settings

logger = logging.getLogger(__name__)


async def fetch_olx_api(
    vehicle_type: str = "carros",
    page: int = 1,
    limit: int = 40,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Fetches listings from OLX Portugal internal API.
    
    Endpoint: https://www.olx.pt/api/v1/offers/
    
    Headers imitam app Android OLX. API pública, não precisa auth.
    """
    url = "https://www.olx.pt/api/v1/offers/"
    
    # category_id: 378 = carros, 379 = motos (Portugal)
    category_id = 379 if vehicle_type == "motos" else 378
    
    params = {
        "offset": (page - 1) * limit,
        "limit": limit,
        "category_id": category_id,
        "sort_by": "created_at:desc",
        "filter_refiners": "spell_checker",
    }
    
    # Add filters if provided
    if filters:
        if filters.get("brand"):
            params["filter[make]"] = filters["brand"]
        if filters.get("min_price"):
            params["filter[price_from]"] = filters["min_price"]
        if filters.get("max_price"):
            params["filter[price_to]"] = filters["max_price"]
    
    headers = {
        "User-Agent": "OLX/6.70.0 (Android; Android 14; pt-PT)",
        "Accept": "application/json",
        "Accept-Language": "pt-PT,pt;q=0.9",
        "X-OLX-App-Version": "6.70.0",
        "X-OLX-Platform": "android",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            logger.debug(f"[OLX_API] Request: {url} (page {page})")
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.warning(f"[OLX_API] HTTP {response.status_code}")
                return []
            
            data = response.json()
            
            # Parse OLX API response format
            listings = []
            
            # Handle OLX API response format
            if isinstance(data, dict):
                # Current format: {"data": [...], "metadata": {...}, "links": {...}}
                data_content = data.get("data", [])
                if isinstance(data_content, list):
                    offers = data_content  # Offers are directly in data array
                else:
                    offers = data_content.get("offers", [])  # Fallback to old format
            elif isinstance(data, list):
                offers = data  # Direct list format
            else:
                logger.warning(f"[OLX_API] Unexpected response format: {type(data)}")
                return []
            
            for offer in offers:
                try:
                    listing = {
                        "source": "OLX",
                        "source_id": str(offer.get("id", "")),
                        "title": offer.get("title", ""),
                        "url": offer.get("url", ""),
                        "price": _extract_price_from_params(offer.get("params", [])),
                        "location": _extract_location_olx(offer.get("location", {})),
                        "images": _extract_images_olx(offer.get("photos", [])),
                        "description": offer.get("description", ""),  # CRITICAL: Extract description for AI LLM
                        "params": offer.get("params", {}),  # km, year, fuel, etc.
                        "created_at": offer.get("created_at") or offer.get("created_time"),
                    }
                    
                    # Extract vehicle details from params
                    params_dict = {p.get("key", "").lower(): p.get("value", "") 
                                  for p in offer.get("params", [])}
                    
                    logger.debug(f"[OLX_API] Params dict: {params_dict}")
                    
                    listing["year"] = _parse_int(
                        params_dict.get("year")
                        or params_dict.get("ano")
                    )
                    listing["km"] = _parse_int(
                        params_dict.get("mileage")
                        or params_dict.get("quilometros")
                        or params_dict.get("quilometragem")
                        or params_dict.get("km")
                    )

                    fuel_raw = (
                        params_dict.get("fuel_type")
                        or params_dict.get("combustivel")
                        or params_dict.get("combustível")
                    )
                    transmission_raw = params_dict.get("gearbox") or params_dict.get("transmission")

                    listing["fuel_type"] = _extract_label_value(fuel_raw)
                    listing["transmission"] = _extract_label_value(transmission_raw)

                    brand, model = _extract_brand_model_from_title(listing.get("title", ""))
                    listing["brand"] = brand
                    listing["model"] = model
                    
                    logger.debug(f"[OLX_API] Extracted listing: {listing.get('title')} - Year: {listing.get('year')}, Price: {listing.get('price')}")
                    
                    if listing["title"] and listing["url"]:
                        listings.append(listing)
                        
                except Exception as e:
                    logger.debug(f"[OLX_API] Parse error: {e}")
                    continue
            
            logger.info(f"[OLX_API] Fetched {len(listings)} listings (page {page})")
            return listings
            
    except httpx.HTTPError as e:
        logger.error(f"[OLX_API] HTTP error: {e}")
        raise
    except Exception as e:
        logger.error(f"[OLX_API] Error: {e}")
        raise


def _extract_price_from_params(params: List[Dict]) -> Optional[float]:
    """Extract price from OLX params array"""
    if not params:
        return None
    
    for param in params:
        if param.get("key") == "price":
            price_data = param.get("value", {})
            if isinstance(price_data, dict):
                amount = price_data.get("value", 0)
                try:
                    return float(amount) if amount else None
                except (ValueError, TypeError):
                    return None
    return None


def _extract_price_olx(price_data: Dict) -> Optional[float]:
    """Extrai preço do formato OLX API (legacy)"""
    if not price_data:
        return None
    try:
        value = price_data.get("value", {})
        amount = value.get("amount", 0)
        return float(amount) if amount else None
    except (ValueError, TypeError):
        return None


class APIClient:
    """Legacy compatibility wrapper for API helper functions."""

    async def fetch_olx_api(self, *args, **kwargs):
        return await fetch_olx_api(*args, **kwargs)

    async def fetch_standvirtual_api(self, *args, **kwargs):
        return await fetch_standvirtual_api(*args, **kwargs)


def _extract_label_value(value: Any) -> str:
    """Extract text from OLX API value objects."""
    if value is None:
        return ""
    if isinstance(value, dict):
        label = value.get("label")
        key = value.get("key")
        if isinstance(label, str) and label.strip():
            return label.strip().lower()
        if isinstance(key, str) and key.strip():
            return key.strip().lower()
        return ""
    if isinstance(value, str):
        return value.strip().lower()
    return str(value).strip().lower()


def _extract_brand_model_from_title(title: Any) -> tuple[str, str]:
    """Best-effort brand/model parser from title for initial coverage."""
    if not isinstance(title, str):
        return "", ""
    cleaned = title.strip()
    if not cleaned:
        return "", ""

    parts = cleaned.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _extract_location_olx(location_data: Dict) -> str:
    """Extrai localização do formato OLX API"""
    if not location_data:
        return ""
    city = location_data.get("city", {})
    region = location_data.get("region", {})
    
    parts = []
    if city.get("name"):
        parts.append(city["name"])
    if region.get("name"):
        parts.append(region["name"])
    
    return ", ".join(parts)


def _extract_images_olx(photos: List[Dict]) -> List[str]:
    """Extrai URLs de imagens"""
    images = []
    for photo in photos:
        url = photo.get("link", "")
        if url:
            # Use larger size if available
            images.append(url.replace(";s=100x100", ";s=800x600"))
    return images


def _parse_int(value: Any) -> Optional[int]:
    """Parse int seguro"""
    if not value:
        return None
    
    # Handle dictionary values from OLX API
    if isinstance(value, dict):
        inner_val = value.get('key') or value.get('value') or value.get('label')
        if inner_val:
            return _parse_int(inner_val)
        return None

    try:
        # Remove não-dígitos
        import re
        digits = re.sub(r"\D", "", str(value))
        return int(digits) if digits else None
    except (ValueError, TypeError):
        return None


async def fetch_standvirtual_api(
    vehicle_type: str = "carros",
    page: int = 1,
    limit: int = 40,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Fetches listings from Standvirtual internal API.
    
    Standvirtual usa GraphQL ou REST endpoints internos.
    """
    # Standvirtual API endpoints (a verificar/testar)
    # Possíveis endpoints:
    # - https://www.standvirtual.com/api/search/
    # - https://www.standvirtual.com/graphql
    
    base_url = "https://www.standvirtual.com/api/offers/"
    
    params = {
        "page": page,
        "limit": limit,
        "category": vehicle_type,
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "pt-PT,pt;q=0.9",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            logger.debug(f"[STANDVIRTUAL_API] Request: {base_url} (page {page})")
            response = await client.get(base_url, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.warning(f"[STANDVIRTUAL_API] HTTP {response.status_code}")
                return []
            
            data = response.json()
            
            # Parse Standvirtual API response format
            listings = []
            offers = data.get("data", {}).get("offers", [])
            
            for offer in offers:
                try:
                    listing = {
                        "source": "STANDVIRTUAL",
                        "source_id": str(offer.get("id", "")),
                        "title": offer.get("title", ""),
                        "url": offer.get("url", ""),
                        "price": _extract_price_standvirtual(offer.get("price", {})),
                        "location": offer.get("location", ""),
                        "images": offer.get("images", []),
                        "year": offer.get("year"),
                        "km": offer.get("km"),
                        "fuel_type": offer.get("fuel_type", ""),
                        "transmission": offer.get("transmission", ""),
                    }
                    
                    if listing["title"] and listing["url"]:
                        listings.append(listing)
                        
                except Exception as e:
                    logger.debug(f"[STANDVIRTUAL_API] Parse error: {e}")
                    continue
            
            logger.info(f"[STANDVIRTUAL_API] Fetched {len(listings)} listings (page {page})")
            return listings
            
    except httpx.HTTPError as e:
        logger.error(f"[STANDVIRTUAL_API] HTTP error: {e}")
        raise
    except Exception as e:
        logger.error(f"[STANDVIRTUAL_API] Error: {e}")
        raise


def _extract_price_standvirtual(price_data: Dict) -> Optional[float]:
    """Extrai preço do formato Standvirtual API"""
    if not price_data:
        return None
    try:
        amount = price_data.get("amount", 0)
        return float(amount) if amount else None
    except (ValueError, TypeError):
        return None
