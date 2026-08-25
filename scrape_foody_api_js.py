#!/usr/bin/env python3
"""
Scrape Foody using JS API calls from within page context
"""
import json
import time
import sys
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
    print("Login may have failed")
    return True

def call_api(page, page_num, page_size=50):
    """Call API via JavaScript"""
    api_url = f"https://www.foody.vn/__get/Directory/IndexAsync?ds=Restaurant&page={page_num}&pageSize={page_size}&q=&Lat=0&Lon=0&vt=row&st=7&append=true"

    script = f"""
    fetch('{api_url}')
        .then(r => r.json())
        .then(d => {{ window.__apiResult = d; }})
        .catch(e => {{ window.__apiError = e.message; }});
    """

    page.evaluate(script)
    page.wait_for_timeout(2000)

    result = page.evaluate('window.__apiResult')
    error = page.evaluate('window.__apiError')

    if error:
        return None, error

    return result, None

def main():
    print('=' * 60)
    print('Foody Scraper - JS API')
    print('=' * 60)

    all_venues = []
    seen_ids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # Login
        if not login(page):
            print("Login failed, exiting")
            return

        # Navigate to main page
        print("Loading main page...")
        page.goto('https://www.foody.vn/ho-chi-minh/', wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(3000)

        # Test API call
        print("Testing API...")
        data, err = call_api(page, 1, 50)

        if err:
            print(f"API Error: {err}")
        elif data:
            print(f"API OK! Total: {data.get('totalResult', 'N/A')}")
            print(f"Items: {len(data.get('searchItems', []))}")

            # Extract venues
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

            print(f"Extracted {len(all_venues)} venues")
        else:
            print("No data returned")

        browser.close()

    # Save
    with open(OUTPUT_DIR / 'foody_js_api.json', 'w', encoding='utf-8') as f:
        json.dump({'venues': all_venues, 'total': len(all_venues)}, f, ensure_ascii=False, indent=2)

    print(f"\nSaved: {len(all_venues)} venues")

if __name__ == '__main__':
    main()
