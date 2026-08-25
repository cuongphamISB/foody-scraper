#!/usr/bin/env python3
"""
Backfill missing pages from Foody scraper
Scrapes specific pages that were missed due to rate limiting
"""
import json
import time
import random
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
BATCH_SIZE = 50
DELAY = 20  # seconds between pages
MAX_RETRIES = 3

# Pages that were missed (from the log)
# Will be updated from progress.json if available
MISSING_PAGES = []  # Auto-detected from progress.json

def get_missing_pages():
    """Get missing pages from progress.json"""
    f = OUTPUT_DIR / 'progress.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            scraped = set(data.get('scraped_pages', []))
            last_page = data.get('last_page', 0)
            venues_count = len(data.get('venues', []))

            # Calculate what page we started from (first page with data)
            # We scrape from page 19 onwards (after login + warmup)
            start_page = 19

            # Pages that were attempted = start_page to last_page
            attempted = set(range(start_page, last_page + 1))

            # Missing = attempted - scraped
            missing = sorted(attempted - scraped)
            return missing
    return []

def load_existing():
    """Load existing venues"""
    f = OUTPUT_DIR / 'foody_full.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('venues', [])
    return []

def save_backfill(backfill_venues):
    """Save backfill results"""
    f = OUTPUT_DIR / 'foody_backfill.json'
    with open(f, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': backfill_venues,
            'pages': len(MISSING_PAGES),
            'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

def scrape_page(page, page_num):
    """Scrape a single page"""
    responses = []

    def on_response(response):
        url = response.url
        if '__get/Directory/IndexAsync' in url:
            try:
                body = response.body().decode('utf-8', errors='ignore')
                if body.strip().startswith('{'):
                    responses.append(json.loads(body))
            except:
                pass

    page.on('response', on_response)

    def handle_route(route):
        url = route.request.url
        if '__get/Directory/IndexAsync' in url:
            url = re.sub(r'page=\d+', f'page={page_num}', url)
            url = re.sub(r'pageSize=\d+', f'pageSize={BATCH_SIZE}', url)
            route.continue_(url=url)
        else:
            route.continue_()

    page.route('**/__get/Directory/IndexAsync**', handle_route)

    try:
        page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                  wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)
    except:
        pass

    return responses[0] if responses else None

def main():
    # Get missing pages from progress
    global MISSING_PAGES
    MISSING_PAGES = get_missing_pages()

    print('=' * 60)
    print('FOODY BACKFILL SCRAPER')
    print('=' * 60)
    print(f'Pages to backfill: {len(MISSING_PAGES)}')
    if MISSING_PAGES:
        print(f'Pages: {MISSING_PAGES[:10]}{"..." if len(MISSING_PAGES) > 10 else ""}')
    print()

    # Load existing data
    existing = load_existing()
    existing_ids = {v['id'] for v in existing}
    print(f'Existing venues: {len(existing)}')

    backfill_venues = []
    backfill_ids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36'
        )

        # Login
        page = context.new_page()
        print('Logging in...')
        page.goto('https://id.foody.vn/dang-nhap', wait_until='domcontentloaded', timeout=45000)
        page.wait_for_timeout(2000)
        page.fill('#Email', 'simonhart0907@gmail.com')
        page.fill('#Password', '3ypY7rQ9v3n@JJh')
        page.check('#RememberMe')
        page.click('input[type="submit"]')
        page.wait_for_timeout(6000)

        if '/tai-khoan' in page.url:
            print('Login OK!')
        else:
            print('Login may have failed')

        print(f'Waiting 60s for rate limits to clear...')
        time.sleep(60)

        success_count = 0
        fail_count = 0

        for page_num in MISSING_PAGES:
            # Retry logic
            data = None
            for attempt in range(MAX_RETRIES):
                data = scrape_page(page, page_num)
                if data and data.get('searchItems'):
                    break
                if attempt < MAX_RETRIES - 1:
                    print(f'  Retry {attempt + 1} for page {page_num}...')
                    time.sleep(DELAY * (attempt + 1))

            if data and data.get('searchItems'):
                items = data['searchItems']
                new = 0
                duplicates = 0

                for item in items:
                    vid = f"foody-{item['Id']}"
                    if vid in existing_ids:
                        duplicates += 1
                    elif vid not in backfill_ids:
                        backfill_ids.add(vid)
                        new += 1

                        cuisines = [
                            c['Name'] for c in item.get('Cuisines', [])
                            if isinstance(c, dict)
                        ]

                        venue = {
                            'id': vid,
                            'name': item.get('Name', ''),
                            'address': item.get('Address', ''),
                            'district': item.get('District', ''),
                            'city': item.get('City', ''),
                            'rating': item.get('AvgRating'),
                            'reviews': item.get('TotalReview'),
                            'cuisines': cuisines,
                            'lat': item.get('Latitude'),
                            'lng': item.get('Longitude'),
                            'phone': item.get('Phone', ''),
                            'url': item.get('Url', ''),
                        }
                        backfill_venues.append(venue)

                print(f'Page {page_num}: {len(items)} items (+{new} new, {duplicates} dup) | total backfill: {len(backfill_venues)}')
                success_count += 1
            else:
                print(f'Page {page_num}: FAILED')
                fail_count += 1

            # Delay with jitter
            delay = DELAY + random.uniform(-5, 5)
            time.sleep(max(5, delay))

        page.close()
        browser.close()

    # Save backfill results
    save_backfill(backfill_venues)

    print()
    print('=' * 60)
    print(f'BACKFILL COMPLETE')
    print(f'Success: {success_count}/{len(MISSING_PAGES)}')
    print(f'Failed: {fail_count}')
    print(f'New venues scraped: {len(backfill_venues)}')
    print(f'Saved to: {OUTPUT_DIR / "foody_backfill.json"}')
    print()
    print('To merge with existing data, run:')
    print('  python merge_foody_data.py')

if __name__ == '__main__':
    main()
