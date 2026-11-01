import asyncio, os, sys, traceback
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.browser.manager.browser_manager import browser_manager

async def test_restart():
    try:
        # First get a page
        page = await browser_manager.get_page()
        print('Initial page URL:', page.url)
        # Simulate browser closure
        await browser_manager.close()
        print('Browser closed')
        # Attempt to get page again, should restart
        page2 = await browser_manager.get_page()
        print('Recovered page URL:', page2.url)
    except Exception as e:
        print('Exception during test:', e)
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_restart())

