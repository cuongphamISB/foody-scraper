#!/usr/bin/env python3
"""
Scrape Foody by intercepting XHR responses
"""
import json
import time
import sys
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

all_venues = []
seen_ids = set()

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
    return True

def route_handler(route):
    """Intercept API responses"""
    url = route.request.url

    if '__get/Directory/IndexAsync' in url:
        route.continue_()
    else:
        route.continue_()

def main():
    global all_venues, seen_ids

    print('=' * 60)
    print('Foody Scraper - Route Interception')
    print('=' * 60)

    api_data = []
    api_count = 0

    def on_response(response):
        global api_count
        url = response.url
        if '__get/Directory/IndexAsync' in url:
            try:
                body = response.body()
                text = body.decode('utf-8', errors='ignore')
                data = json.loads(text)
                api_count += 1
                print(f"API #{api_count}: total={data.get('totalResult', '?')}, items={len(data.get('searchItems', []))}")
                api_data.append(data)
            except Exception as e:
                print(f"API parse error: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # Login
        if not login(page):
            return

        # Navigate to main page
        print("Loading main page...")
        page.goto('https://www.foody.vn/ho-chi-minh/', wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(3000)

        # Register response handler
        page.on('response', on_response)

        # Scroll to trigger more loads
        print("Scrolling to load more...")
        for i in range(20):
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(1500)

            # Click "Xem them" if exists
            try:
                btn = page.query_selector('button:has-text("Xem thêm")')
                if btn:
                    btn.click()
                    page.wait_for_timeout(2000)
            except:
                pass

        browser.close()

    print(f"\n=== Total API responses: {len(api_data)} ===")

    # Extract venues
    for data in api_data:
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

    # Save
    with open(OUTPUT_DIR / 'foody_route.json', 'w', encoding='utf-8') as f:
        json.dump({'venues': all_venues, 'total': len(all_venues)}, f, ensure_ascii=False, indent=2)

    print(f"Extracted: {len(all_venues)} unique venues")
    print(f"Saved to: {OUTPUT_DIR / 'foody_route.json'}")

if __name__ == '__main__':
    main()
