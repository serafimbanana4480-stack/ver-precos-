#!/usr/bin/env python3
"""
Debug Standvirtual extraction process
"""
import asyncio
from seleniumbase import SB
from bs4 import BeautifulSoup
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_standvirtual():
    """Debug the Standvirtual extraction process"""
    url = "https://www.standvirtual.com/carros"
    
    print(f"[*] Debugging Standvirtual extraction for: {url}")
    
    try:
        with SB(uc=True, headless=False) as sb:
            print("[*] Launching browser...")
            sb.uc_open_with_reconnect(url, reconnect_time=4)
            print("[*] Waiting for page to fully load...")
            await asyncio.sleep(8)
            
            html = sb.get_page_source()
            soup = BeautifulSoup(html, 'lxml')
            
            print(f"[*] HTML length: {len(html)} characters")
            
            # Find all car listing links
            car_links = soup.find_all('a', href=re.compile(r'/carros/[^/]+$'))
            print(f"[*] Found {len(car_links)} car listing links")
            
            # Analyze first few links
            for i, link in enumerate(car_links[:5]):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                print(f"\n--- Link {i+1} Analysis ---")
                print(f"URL: {href}")
                print(f"Text: '{text}'")
                print(f"Length: {len(text)}")
                
                # Check if it's navigation data
                text_lower = text.lower().strip()
                is_navigation = False
                
                # Check navigation patterns
                nav_patterns = ['ver anúncios', 'carros novos', 'novocarros novos']
                for pattern in nav_patterns:
                    if pattern in text_lower:
                        is_navigation = True
                        break
                
                # Check location count pattern
                if re.match(r'^[a-z]+[\d]+\s+[\d]+$', text_lower):
                    is_navigation = True
                
                print(f"Is navigation: {is_navigation}")
                
                # Check parent container
                parent = link.parent
                if parent:
                    parent_text = parent.get_text()[:200]
                    print(f"Parent text: '{parent_text}'")
                
                print("-" * 50)
    
    except Exception as e:
        print(f"[ERROR] Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_standvirtual())
