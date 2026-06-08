#!/usr/bin/env python3
"""
Custom Standvirtual extractor for complex HTML structure
"""
import os
import re
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
import logging
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

class StandvirtualExtractor:
    """Custom extractor for Standvirtual's complex HTML structure"""
    
    def __init__(self):
        self.proxy_manager = ProxyManager()
        self.price_patterns = [
            r'€?\s*[\d.,]+',
            r'[\d.,]+\s*€',
            r'(\d{1,3}(?:[.,]\d{3})?)\s*€',
            r'(\d{1,3})(?=\s*€)',
        ]
    
    def extract_listings(self, soup: BeautifulSoup, max_listings: int = 50) -> List[Dict[str, Any]]:
        """Extract listings from Standvirtual HTML"""
        listings = []
        
        # Try to find actual vehicle listings (not location navigation)
        # Look for links that point to specific vehicle pages
        vehicle_links = soup.find_all('a', href=re.compile(r'/carros/[^/]+/[^/]+$'))
        
        logger.info(f"Found {len(vehicle_links)} vehicle listing links")
        
        # If no direct vehicle links found, try alternative patterns
        if not vehicle_links:
            # Look for links with anuncio or specific vehicle patterns
            vehicle_links = soup.find_all('a', href=re.compile(r'/anuncio'))
            logger.info(f"Found {len(vehicle_links)} anuncio links")
        
        if not vehicle_links:
            # Look for any links that might be vehicle listings
            # Exclude obvious navigation links
            all_links = soup.find_all('a', href=True)
            vehicle_links = []
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Skip navigation and location links
                if (self._is_navigation_data(text) or 
                    '?' in href or 
                    'search' in href.lower() or
                    'brand_program_id' in href.lower()):
                    continue
                
                # Include links that look like vehicle listings
                if ('/carros/' in href and 
                    len(text) > 5 and 
                    not re.match(r'^[a-z]+[\d]+\s+[\d]+$', text.lower())):
                    vehicle_links.append(link)
            
            logger.info(f"Found {len(vehicle_links)} potential vehicle links after filtering")
        
        for i, link in enumerate(vehicle_links[:max_listings]):
            try:
                listing_data = self._extract_single_listing(link, soup)
                if listing_data:
                    listings.append(listing_data)
                    logger.info(f"Extracted listing {i+1}: {listing_data.get('title', 'N/A')}")
                else:
                    logger.warning(f"Failed to extract listing {i+1}")
            except Exception as e:
                logger.error(f"Error extracting listing {i+1}: {e}")
        
        return listings
    
    def _extract_single_listing(self, link_element, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract data from a single listing element"""
        href = link_element.get('href', '')
        if not href or '/carros/' not in href:
            return None
        
        # Skip navigation/filter links that aren't actual listings
        if any(skip in href.lower() for skip in ['?', 'search', 'filter', 'brand_program_id', '/carros$', '/carros/']):
            return None
        
        # Get link text as fallback title
        link_text = link_element.get_text(strip=True)
        
        # Skip if link text looks like navigation/location data
        if self._is_navigation_data(link_text):
            return None
        
        # Find parent container with detailed info
        parent = link_element.parent
        level = 0
        listing_data = {
            'url': href,
            'title': None,
            'price': None,
            'location': None,
            'year': None,
            'km': None
        }
        
        # Use link text as title fallback
        if link_text and len(link_text.strip()) > 3:
            listing_data['title'] = link_text.strip()
        
        # Traverse up to find price and other details
        while parent and level < 6:
            level += 1
            parent_text = parent.get_text()
            
            # Extract price using patterns
            price = self._extract_price_from_text(parent_text)
            if price and not listing_data['price']:
                listing_data['price'] = price
            
            # Extract year
            year = self._extract_year_from_text(parent_text)
            if year and not listing_data['year']:
                listing_data['year'] = year
            
            # Extract KM
            km = self._extract_km_from_text(parent_text)
            if km and not listing_data['km']:
                listing_data['km'] = km
            
            # Extract location (cities/regions)
            location = self._extract_location_from_text(parent_text)
            if location and not listing_data['location']:
                listing_data['location'] = location
            
            parent = parent.parent
        
        # Clean up extracted data
        listing_data['title'] = self._clean_title(listing_data['title'])
        listing_data['price'] = self._clean_price(listing_data['price'])
        
        # Only return if we have valid vehicle data
        has_vehicle_data = (
            listing_data['title'] and 
            not self._is_navigation_data(listing_data['title'])
        )
        
        return listing_data if has_vehicle_data else None
    
    def _is_navigation_data(self, text: Optional[str]) -> bool:
        """Check if text represents navigation/location data rather than vehicle data"""
        if not text:
            return True
        
        text_lower = text.lower().strip()
        
        # Only skip obvious navigation patterns
        navigation_patterns = [
            'ver anúncios', 'carros novos', 'novocarros novos',
        ]
        
        for pattern in navigation_patterns:
            if pattern in text_lower:
                return True
        
        # Skip location counts like "Lisboa13 057" or "Porto11 447"
        if re.match(r'^[a-z]+[\d]+\s+[\d]+$', text_lower):
            return True
        
        # Don't skip single words anymore - they might be valid car names
        # Allow more listings through and validate at database level
        
        return False
    
    def _extract_price_from_text(self, text: str) -> Optional[str]:
        """Extract price from text using multiple patterns"""
        if not text:
            return None
        
        for pattern in self.price_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Take the first reasonable price match
                for match in matches:
                    if isinstance(match, str):
                        price_str = match
                    else:
                        price_str = match[0] if match[0] else match[1] if len(match) > 1 else None
                    
                    if price_str:
                        # Clean and validate price
                        price_clean = re.sub(r'[^\d.,€]', '', price_str)
                        if price_clean and len(price_clean) > 2:
                            # Convert to standard format
                            if '€' in price_str:
                                return price_clean.replace('.', ',') + '€'
                            return price_clean
                break
        return None
    
    def _extract_year_from_text(self, text: str) -> Optional[str]:
        """Extract year from text"""
        if not text:
            return None
        
        # Look for 4-digit years in reasonable range (1990-2026)
        year_matches = re.findall(r'\b(19|20)\d{2}\b', text)
        for year in year_matches:
            year_int = int(year)
            if 1990 <= year_int <= 2026:
                return year
        return None
    
    def _extract_km_from_text(self, text: str) -> Optional[str]:
        """Extract kilometers from text"""
        if not text:
            return None
        
        # Look for KM patterns
        km_matches = re.findall(r'(\d{1,6}(?:[.,]\d{3})?)\s*km', text, re.IGNORECASE)
        for match in km_matches:
            km_str = match[0] if isinstance(match, tuple) else match
            if km_str:
                return km_str.replace('.', ',') + ' km'
        return None
    
    def _extract_location_from_text(self, text: str) -> Optional[str]:
        """Extract location from text"""
        if not text:
            return None
        
        # Common Portuguese cities/regions
        locations = [
            'Lisboa', 'Porto', 'Braga', 'Faro', 'Aveiro', 'Santarém', 'Leiria',
            'Coimbra', 'Vila Real', 'Viana do Castelo', 'Viseu', 'Setúbal',
            'Évora', 'Portalegre', 'Beja', 'Guarda', 'Ilha da Madeira', 'Ilha de São Miguel'
        ]
        
        for location in locations:
            if location.lower() in text.lower():
                return location
        
        return None
    
    def _clean_title(self, title: Optional[str]) -> Optional[str]:
        """Clean extracted title"""
        if not title:
            return None
        
        # Remove common prefixes and clean
        title = title.strip()
        
        # Remove navigation/menu items
        nav_items = ['Carros novos', 'Ver carros novos', 'NOVOCarros novos']
        for item in nav_items:
            if title.startswith(item):
                return None
        
        # Remove location-only titles
        if title.lower() in [loc.lower() for loc in ['Lisboa', 'Porto', 'Braga', 'Faro']]:
            return None
        
        # Clean up extra whitespace and special chars
        title = re.sub(r'\s+', ' ', title)
        title = title.strip()
        
        return title if len(title) > 3 else None
    
    def _clean_price(self, price: Optional[str]) -> Optional[str]:
        """Clean extracted price"""
        if not price:
            return None
        
        # Remove currency symbols and clean
        price = price.strip()
        price = re.sub(r'[^\d.,€]', '', price)
        
        # Validate it's a reasonable price
        if re.match(r'^\d{1,6}(?:[.,]\d{0,3})?$', price):
            return price
        
        return None
