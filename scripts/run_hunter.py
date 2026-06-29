import asyncio
import logging
import sys
from services.deal_hunter import start_hunter

# Setup logging with UTF-8 support
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("hunter.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

if __name__ == "__main__":
    print("AutoDeal IA Hunter - Hardened Edition")
    print("Starting parallel hunt cycle...")
    asyncio.run(start_hunter())
    print("\nCycle complete. Open the Dashboard with 'python app.py'")
