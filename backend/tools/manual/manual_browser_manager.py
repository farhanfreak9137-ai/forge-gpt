import asyncio, sys, traceback, os
# Ensure backend package is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.browser.manager.browser_manager import browser_manager
async def main():
    try:
        page = await browser_manager.get_page()
        print('Page URL:', page.url)
        # Try to retrieve messages to ensure page usable
        msgs = await browser_manager.get_current_chat_messages()
        print('Extracted', len(msgs), 'messages')
    except Exception as e:
        print('Exception:', e)
        traceback.print_exc()
        # Force restart
        await browser_manager.close()
        # Retry
        try:
            page = await browser_manager.get_page()
            print('Recovered page URL:', page.url)
        except Exception as e2:
            print('Recovery failed:', e2)
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
