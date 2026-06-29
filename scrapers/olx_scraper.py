import requests
from bs4 import BeautifulSoup
import time
import re

def scrape_olx(max_pages=1):
    """Scrape OLX.pt for car listings."""
    listings = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for page in range(1, max_pages + 1):
        url = f'https://www.olx.pt/carros/?page={page}'
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # OLX uses data-cy attributes or specific classes
        articles = soup.select('[data-cy="l-card"]')
        for article in articles:
            # Extract title
            title_elem = article.select_one('[data-cy="ad-card-title"]')
            title = title_elem.text.strip() if title_elem else ''
            
            # Extract price
            price_elem = article.select_one('[data-testid="ad-price"]')
            price_text = price_elem.text.strip() if price_elem else ''
            price = float(re.sub(r'[^\d]', '', price_text)) if price_text else 0
            
            if title and price > 0:
                listings.append({
                    'title': title,
                    'price': price,
                    'url': article.select_one('a')['href'] if article.select_one('a') else ''
                })
        
        time.sleep(1)
    
    return listings

if __name__ == '__main__':
    results = scrape_olx(max_pages=1)
    print(f'Encontrados {len(results)} listings no OLX')
    for r in results[:3]:
        print(f'  {r["title"][:40]} - €{r["price"]}')
