#!/usr/bin/env python3
"""
Foody Scraper - Mobile iPhone Approach
Uses mobile user agent which appears to have less rate limiting
"""
import json
import time
import random
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === CONFIG ===
BATCH_SIZE = 50
DELAY = 10  # seconds between requests
SAVE_EVERY = 25

def load_progress():
    f = OUTPUT_DIR / 'progress.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('venues', []), data.get('last_page', 0)
    return [], 0

def save_progress(venues, last_page):
    f = OUTPUT_DIR / 'progress.json'
    with open(f, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'last_page': last_page,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False)

def scrape_page(page, page_num):
    responses = []

    def on_response(response):
        if 'IndexAsync' in response.url:
            try:
                body = response.body().decode('utf-8', errors='ignore')
                if body.strip().startswith('{'):
                    responses.append(json.loads(body))
            except:
                pass

    page.on('response', on_response)

    def handle_route(route):
        url = route.request.url
        if 'IndexAsync' in url:
            url = re.sub(r'page=\d+', f'page={page_num}', url)
            url = re.sub(r'pageSize=\d+', f'pageSize={BATCH_SIZE}', url)
            route.continue_(url=url)
        else:
            route.continue_()

    page.route('**/IndexAsync**', handle_route)

    try:
        page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                  wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)
    except:
        pass

    return responses[0] if responses else None

def main():
    print('=' * 60)
    print('FOODY SCRAPER - MOBILE EDITION')
    print('=' * 60)
    print(f'Batch: {BATCH_SIZE}/page | Delay: {DELAY}s')
    print()

    venues, start_page = load_progress()
    seen_ids = {v['id'] for v in venues}
    print(f'Loaded: {len(venues)} venues from page {start_page}')

    # Start fresh browser for clean session
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        while True:
            # Create new context and page
            context = browser.new_context(
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
            )
            page = context.new_page()
            page.set_viewport_size({'width': 375, 'height': 812})

            # Login
            print('Logging in...')
            page.goto('https://id.foody.vn/dang-nhap',
                      wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(2000)
            page.fill('#Email', 'simonhart0907@gmail.com')
            page.fill('#Password', '3ypY7rQ9v3n@JJh')
            page.check('#RememberMe')
            page.click('input[type="submit"]')
            page.wait_for_timeout(6000)

            if '/tai-khoan' in page.url:
                print('✓ Login OK')
            else:
                print('⚠ Login may have failed')

            # Scrape session
            consecutive_fail = 0

            for num in range(start_page + 1, start_page + 100):  # 100 pages per login
                start = time.time()

                data = scrape_page(page, num)

                if data and data.get('searchItems'):
                    items = data['searchItems']
                    new_count = 0

                    for item in items:
                        vid = f"foody-{item['Id']}"
                        if vid not in seen_ids:
                            seen_ids.add(vid)
                            new_count += 1

                            cuisines = [c['Name'] for c in item.get('Cuisines', [])
                                      if isinstance(c, dict)]

                            venues.append({
                                'id': vid,
                                'name': item.get('Name', ''),
                                'address': item.get('Address', ''),
                                'district': item.get('District', ''),
                                'rating': item.get('AvgRating'),
                                'reviews': item.get('TotalReview'),
                                'cuisines': cuisines,
                                'lat': item.get('Latitude'),
                                'lng': item.get('Longitude'),
                            })

                    elapsed = time.time() - start
                    print(f'Page {num}: {len(items)} items (+{new_count}) | {len(venues)} total | {elapsed:.1f}s')

                    save_progress(venues, num)
                    consecutive_fail = 0

                    # Check if complete
                    total = data.get('totalResult', 0)
                    if len(venues) >= total:
                        print(f'\n✓ Complete! Got all {total} venues')
                        break
                else:
                    print(f'Page {num}: FAILED')
                    consecutive_fail += 1
                    save_progress(venues, num)

                time.sleep(DELAY)

                # Restart session after too many fails
                if consecutive_fail >= 5:
                    print(f'\n⚠ Too many fails. Restarting session...')
                    page.close()
                    context.close()
                    break

            page.close()
            context.close()

            start_page = num  # Update for next session
            time.sleep(30)  # Wait before new session

            if consecutive_fail < 5:
                break

    # Final save
    output = OUTPUT_DIR / 'foody_full.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'source': 'foody.vn',
            'completed_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*60}')
    print(f'DONE! Total: {len(venues)} venues')
    print(f'Saved: {output}')

if __name__ == '__main__':
    main()
