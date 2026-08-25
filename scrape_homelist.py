#!/usr/bin/env python3
"""
Scrape Foody HomeListPlace API by scrolling
"""
import json
import time
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def login(page):
    print("Logging in...")
    page.goto('https://id.foody.vn/dang-nhap', wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(2000)
    page.fill('#Email', 'simonhart0907@gmail.com')
    page.fill('#Password', '3ypY7rQ9v3n@JJh')
    page.check('#RememberMe')
    page.click('input[type="submit"]')
    page.wait_for_timeout(6000)
    return '/tai-khoan' in page.url

def main():
    global all_venues, seen_ids
    all_venues = []
    seen_ids = set()
    api_data = []
    total_venues = 0

    def on_response(response):
        url = response.url
        if '__get/Place/HomeListPlace' in url and 'type=1' in url:
            try:
                body = response.body().decode('utf-8', errors='ignore')
                data = json.loads(body)
                api_data.append(data)
            except:
                pass

    print('=' * 60)
    print('Foody HomeListPlace Scraper')
    print('=' * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.on('response', on_response)

        login(page)

        print("Loading main page...")
        page.goto('https://www.foody.vn/ho-chi-minh/', wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)

        # Scroll to load more
        print("Scrolling to trigger API calls...")
        last_api_count = 0
        no_new_count = 0

        for i in range(100):
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(1500)

            # Try clicking "Xem them" or load more
            for btn_text in ['Xem thêm', 'Xem thêm nữa', 'Load more']:
                try:
                    btn = page.query_selector(f'button:has-text("{btn_text}")')
                    if btn and btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(2000)
                except:
                    pass

            current_count = len(api_data)
            if current_count > last_api_count:
                no_new_count = 0
                last_api_count = current_count
            else:
                no_new_count += 1

            if i % 10 == 0:
                total_items = sum(len(d.get('Items', [])) for d in api_data)
                print(f"Round {i}: {current_count} API calls, {total_items} items")

            if no_new_count >= 5:
                print("No new API calls for 5 rounds, stopping")
                break

        browser.close()

    # Extract venues
    for data in api_data:
        for item in data.get('Items', []):
            vid = item.get('Id')
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                all_venues.append({
                    'id': f"foody-{vid}",
                    'name': item.get('Name', ''),
                    'address': item.get('Address', ''),
                    'district': item.get('District', ''),
                    'city': item.get('City', ''),
                    'rating': item.get('AvgRating'),
                    'review_count': item.get('TotalReviews'),
                    'cuisines': [c.get('Name', '') for c in item.get('LstCuisine', []) if isinstance(c, dict)],
                    'lat': item.get('Latitude'),
                    'lng': item.get('Longitude'),
                    'phone': item.get('Phone', ''),
                    'url': item.get('Url', ''),
                    'price_min': item.get('PriceMin'),
                    'price_max': item.get('PriceMax'),
                    'has_booking': item.get('HasBooking'),
                    'has_delivery': item.get('HasDelivery'),
                })

    # Save
    with open(OUTPUT_DIR / 'foody_homelist.json', 'w', encoding='utf-8') as f:
        json.dump({
            'venues': all_venues,
            'total_venues': len(all_venues),
            'api_calls': len(api_data),
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"API calls: {len(api_data)}")
    print(f"Venues extracted: {len(all_venues)}")
    print(f"Saved to: {OUTPUT_DIR / 'foody_homelist.json'}")

if __name__ == '__main__':
    main()
