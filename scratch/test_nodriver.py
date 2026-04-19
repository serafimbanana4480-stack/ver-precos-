import asyncio
import sys

async def test_nodriver():
    import nodriver as uc
    browser = await uc.start(headless=True)
    page = await browser.get('about:blank')
    res1 = await page.evaluate("window.scrollBy(0, 500)")
    print(f"res1: {res1}")
    res2 = await page.get_content()
    print(f"res2 len: {len(res2) if res2 else None}")
    
    # check browser.stop()
    import inspect
    print(f"Is browser.stop async? {inspect.iscoroutinefunction(browser.stop)}")
    
    browser.stop()

if __name__ == '__main__':
    asyncio.run(test_nodriver())
