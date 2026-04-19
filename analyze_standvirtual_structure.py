#!/usr/bin/env python3
"""
Deep analysis of Standvirtual HTML structure to create working selectors
"""
import asyncio
from seleniumbase import SB
from bs4 import BeautifulSoup
import time
import re

async def analyze_standvirtual():
    """Analyze Standvirtual structure to find working selectors"""
    url = "https://www.standvirtual.com/carros"
    
    print(f"[*] Deep analysis of Standvirtual structure: {url}")
    
    try:
        with SB(uc=True, headless=False) as sb:
            print("[*] Launching browser...")
            sb.uc_open_with_reconnect(url, reconnect_time=4)
            print("[*] Waiting for page to fully load...")
            time.sleep(8)
            
            html = sb.get_page_source()
            soup = BeautifulSoup(html, 'html.parser')
            
            print(f"[*] HTML length: {len(html)} characters")
            
            # Look for actual listing containers
            print("\n[*] Looking for listing containers...")
            
            # Common patterns for car listings
            potential_containers = [
                {'name': 'article tags', 'selector': 'article'},
                {'name': 'div with car classes', 'selector': 'div[class*="car"]'},
                {'name': 'div with listing classes', 'selector': 'div[class*="listing"]'},
                {'name': 'div with item classes', 'selector': 'div[class*="item"]'},
                {'name': 'a tags with car links', 'selector': 'a[href*="/carros/"]'},
            ]
            
            for container_info in potential_containers:
                elements = soup.select(container_info['selector'])
                print(f"  {container_info['name']}: {len(elements)} elements")
                if elements:
                    # Analyze first element structure
                    first = elements[0]
                    print(f"    First element classes: {first.get('class', [])}")
                    print(f"    First element HTML preview: {str(first)[:300]}...")
            
            # Find actual car listing links and analyze their parents
            print("\n[*] Analyzing car listing links and their structure...")
            car_links = soup.find_all('a', href=re.compile(r'/carros/[^/]+$'))
            print(f"Found {len(car_links)} direct car listing links")
            
            if car_links:
                for i, link in enumerate(car_links[:3]):
                    print(f"\n--- Car Listing {i+1} Analysis ---")
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    print(f"URL: {href}")
                    print(f"Link text: {text[:100]}")
                    
                    # Analyze parent hierarchy
                    parent = link.parent
                    level = 0
                    while parent and level < 5:
                        level += 1
                        tag_name = parent.name
                        classes = parent.get('class', [])
                        print(f"  Parent {level}: <{tag_name}> class={classes}")
                        
                        # Look for price in this level
                        price_text = parent.get_text()
                        if any(char.isdigit() for char in price_text):
                            print(f"    PRICE FOUND: {price_text}")
                        
                        parent = parent.parent
                    
                    print("-" * 50)
            
            # Look for any elements with price-like content
            print("\n[*] Looking for price patterns...")
            price_patterns = [
                r'€?\s*[\d.,]+',
                r'[\d.,]+\s*€',
                r'price.*?[\d.,]+',
                r'preco.*?[\d.,]+',
            ]
            
            for pattern in price_patterns:
                elements = soup.find_all(string=re.compile(pattern, re.IGNORECASE))
                if elements:
                    print(f"Pattern '{pattern}': {len(elements)} matches")
                    for element in elements[:3]:
                        parent = element.parent
                        if parent:
                            print(f"  Parent: <{parent.name}> class={parent.get('class', [])}")
                            print(f"  Text: {parent.get_text()[:100]}")
    
    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(analyze_standvirtual())
