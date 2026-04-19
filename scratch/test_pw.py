import time
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

def test_scrape(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",  # USE REAL CHROME
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        stealth_sync(page)
        
        print(f"Navigating to {url}...")
        page.goto(url)
        time.sleep(3)
        html = page.content()
        
        if "Houston" in html or "Access Denied" in html or "captcha" in html.lower():
            print(f"FAILED to bypass anti-bot on {url}!")
            # Save snippet to show what we hit
            print(html[:500])
        else:
            print(f"SUCCESS! Rendered page length: {len(html)}")
            
        browser.close()

if __name__ == "__main__":
    test_scrape("https://www.olx.pt/carros")
    test_scrape("https://www.standvirtual.com/carros")
