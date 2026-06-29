import asyncio
import argparse
import json
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.ai_extractor import AIExtractor

async def main():
    parser = argparse.ArgumentParser(description="Test AI extraction on an HTML file.")
    parser.add_argument("html_file", help="Path to the HTML file")
    parser.add_argument("source", help="Source name (e.g. olx, standvirtual)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.html_file):
        print(f"Error: File {args.html_file} not found.")
        return
        
    with open(args.html_file, "r", encoding="utf-8") as f:
        html = f.read()
        
    extractor = AIExtractor()
    listings = await extractor.extract_from_html(html, args.source)
    
    print(json.dumps(listings, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
