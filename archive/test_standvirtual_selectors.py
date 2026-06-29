#!/usr/bin/env python3
"""
Test script to examine Standvirtual HTML structure and fix selectors
"""
import asyncio
from seleniumbase import SB
from bs4 import BeautifulSoup
import time

async def test_standvirtual_selectors():
    """Test current Standvirtual selectors and find working ones"""
    url = "https://www.standvirtual.com/carros"
    
    print(f"[*] Testing Standvirtual selectors for: {url}")
    
    try:
        with SB(uc=True, headless=False) as sb:
            print("[*] Launching browser with UC mode...")
            sb.uc_open_with_reconnect(url, reconnect_time=4)
            print("[*] Page loaded, waiting for content...")
            time.sleep(5)
            
            html = sb.get_page_source()
            soup = BeautifulSoup(html, 'html.parser')
            
            print(f"[*] Retrieved HTML length: {len(html)} characters")
            
            # Test current selectors
            current_selectors = {
                'title': [
                    'h2[data-testid="ad-title"] a',
                    'h3.offer-title__link', 
                    'a.offer-title__link'
                ],
                'price': [
                    '[data-testid="ad-price"]',
                    'span.offer-price__number',
                    'dd.offer-item__price'
                ],
                'url': [
                    'h2[data-testid="ad-title"] a',
                    'a.offer-title__link',
                    'a[href*="/carros/"]'
                ],
                'location': [
                    'p[data-testid="ad-location"]',
                    'dd.offer-item__location',
                    'span.offer-item__location'
                ]
            }
            
            print("\n[*] Testing current selectors:")
            for field, selectors in current_selectors.items():
                print(f"\n--- {field.upper()} ---")
                for selector in selectors:
                    try:
                        elements = soup.select(selector)
                        print(f"  {selector}: {len(elements)} elements")
                        if elements:
                            print(f"    Sample: {elements[0].get_text(strip=True)[:100]}")
                    except Exception as e:
                        print(f"  {selector}: ERROR - {e}")
            
            # Look for common listing patterns
            print("\n[*] Looking for common listing patterns...")
            
            # Find all links that look like car listings
            listing_links = soup.find_all('a', href=True)
            car_links = [link for link in listing_links if '/carros/' in link.get('href', '')]
            
            print(f"[*] Found {len(car_links)} car listing links")
            
            if car_links:
                # Analyze first few listings
                for i, link in enumerate(car_links[:3]):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    print(f"\n  Listing {i+1}:")
                    print(f"    URL: {href}")
                    print(f"    Text: {text[:100]}")
                    
                    # Look for parent container
                    parent = link.find_parent()
                    if parent:
                        # Look for price in parent or siblings
                        price_text = parent.get_text()
                        print(f"    Parent text: {price_text[:200]}")
    
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_standvirtual_selectors())
