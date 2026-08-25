#!/usr/bin/env python3
"""
Scrape all venues from Foody using authenticated session
"""
import json
import time
import sys
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# All categories
CATEGORIES = [
    ('Restaurant', 'Nhà hàng/Quán ăn'),
    ('Restaurant', 'Quán ăn'),
    ('Restaurant', 'Nhà hàng'),
    ('Restaurant', 'Café/Dessert'),
    ('Restaurant', 'Buffet'),
    ('Restaurant', 'Bar/Pub'),
    ('Restaurant', 'Tiệm bánh'),
    ('Restaurant', 'Shop Online'),
]

def login(page):
    """Login to Foody"""
    print("Logging in...")
    page.goto('https://id.foody.vn/dang-nhap', wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(2000)

    page.fill('#Email', 'simonhart0907@gmail.com')
    page.fill('#Password', '3ypY7rQ9v3n@JJh')
    page.check('#RememberMe')
    page.click('input[type="submit"]')
    page.wait_for_timeout(6000)

    if '/tai-khoan' in page.url:
        print("Login OK!")
        return True
    print("Login may have failed, continuing...")
    return True

def scrape_page(page, page_num, page_size=50):
    """Scrape one page via API"""
    url = f"https://www.foody.vn/__get/Directory/IndexAsync?ds=Restaurant&page={page_num}&pageSize={page_size}&q=&Lat=0&Lon=0&vt=row&st=7&append=true"

    page.goto(url, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(1000)

    # Try to parse JSON from page
    try:
        content = page.inner_text('body')
        print(f"Response preview: {content[:200]}")
        data = json.loads(content)
        return data
    except Exception as e:
        print(f"Parse error: {e}, content: {page.content()[:500]}")
        return None

def main():
    print('=' * 60)
    print('Foody Full Scraper - Authenticated')
    print('=' * 60)

    all_venues = []
    seen_ids = set()
    page_size = 50
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        login(page)

        # Navigate to main page to establish session
        print("Loading main page...")
        page.goto('https://www.foody.vn/ho-chi-minh/', wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(3000)

        # Get first page to see total
        print("\nFetching first page...")
        data = scrape_page(page, 1, page_size)

        if data and 'searchItems' in data:
            total = data.get('totalResult', 0)
            print(f"Total venues: {total}")

            for item in data.get('searchItems', []):
                vid = item.get('Id', '')
                if vid and vid not in seen_ids:
                    seen_ids.add(vid)
                    all_venues.append({
                        'id': f"foody-{vid}",
                        'name': item.get('Name', ''),
                        'address': item.get('Address', ''),
                        'district': item.get('District', ''),
                        'city': item.get('City', ''),
                        'rating': item.get('AvgRating'),
                        'review_count': item.get('TotalReview'),
                        'cuisines': [c.get('Name', '') for c in item.get('Cuisines', [])],
                        'lat': item.get('Latitude'),
                        'lng': item.get('Longitude'),
                        'phone': item.get('Phone', ''),
                        'url': item.get('Url', ''),
                    })

            print(f"Page 1: {len(data.get('searchItems', []))} venues")
        else:
            print("Failed to get first page")
            return

        # Scrape remaining pages
        max_pages = (total + page_size - 1) // page_size
        print(f"Pages to scrape: {max_pages}")

        for page_num in range(2, max_pages + 1):
            data = scrape_page(page, page_num, page_size)

            if data and 'searchItems' in data:
                items = data.get('searchItems', [])
                if not items:
                    print(f"Page {page_num}: Empty, stopping")
                    break

                for item in items:
                    vid = item.get('Id', '')
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        all_venues.append({
                            'id': f"foody-{vid}",
                            'name': item.get('Name', ''),
                            'address': item.get('Address', ''),
                            'district': item.get('District', ''),
                            'city': item.get('City', ''),
                            'rating': item.get('AvgRating'),
                            'review_count': item.get('TotalReview'),
                            'cuisines': [c.get('Name', '') for c in item.get('Cuisines', [])],
                            'lat': item.get('Latitude'),
                            'lng': item.get('Longitude'),
                            'phone': item.get('Phone', ''),
                            'url': item.get('Url', ''),
                        })

                print(f"Page {page_num}/{max_pages}: {len(items)} venues (total: {len(all_venues)})")
            else:
                print(f"Page {page_num}: Failed, retrying in 5s...")
                time.sleep(5)
                continue

            # Small delay to avoid rate limit
            if page_num % 10 == 0:
                time.sleep(2)

            # Save progress
            if page_num % 50 == 0:
                with open(OUTPUT_DIR / 'progress.json', 'w', encoding='utf-8') as f:
                    json.dump(all_venues, f, ensure_ascii=False, indent=2)
                print(f"Progress saved: {len(all_venues)} venues")

        browser.close()

    # Save final
    with open(OUTPUT_DIR / 'foody_full.json', 'w', encoding='utf-8') as f:
        json.dump(all_venues, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Total venues scraped: {len(all_venues)}")
    print(f"Saved to: {OUTPUT_DIR / 'foody_full.json'}")

if __name__ == '__main__':
    main()
