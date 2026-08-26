#!/usr/bin/env python3
"""
Foody Scraper - GitHub Actions Playwright Edition
Clicks "Xem thêm" button to load more venues
"""
import json
import time
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_FILE = Path('data/foody-batch/venues.json')
PROGRESS_FILE = Path('data/foody-batch/progress.json')
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Config
MAX_CLICK_SESSIONS = 8  # ~5 min each
CLICK_DELAY = 2.0  # Seconds after click

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'venues': [], 'clicks': 0, 'session': 0}

def save_progress(data):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def load_existing():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('venues', [])
    return []

def save_venues(venues):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)
    log(f'Saved {len(venues)} venues')

def scrape_with_button_click(p, venues):
    """Click 'Xem thêm' button to load more venues"""
    seen_ids = {v['id'] for v in venues}
    new_count = 0
    captured = []

    context = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage']
    ).new_context(
        viewport={'width': 1280, 'height': 800},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    )

    page = context.new_page()

    def capture_response(response):
        if 'Directory' in response.url or 'HomeList' in response.url:
            try:
                body = response.body()
                if body:
                    text = body.decode('utf-8', errors='ignore')
                    if text.strip().startswith('{'):
                        data = json.loads(text)
                        captured.append(data)
            except:
                pass

    page.on('response', capture_response)

    try:
        log('Navigating to Foody...')
        page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                 wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)

        log(f'Initial captured: {len(captured)} responses')

        # Click "Xem thêm" button multiple times
        clicks = 0
        max_clicks = 30

        while clicks < max_clicks:
            # Try multiple button selectors
            button = None
            selectors = [
                'button:has-text("Xem thêm")',
                '.btn-more',
                '[class*="more"]',
                'a:has-text("Xem thêm")',
                '.ld-more',
            ]

            for sel in selectors:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        button = btn
                        break
                except:
                    pass

            if not button:
                log(f'No more "Xem thêm" button after {clicks} clicks')
                break

            log(f'Clicking "Xem thêm" ({clicks + 1})...')
            button.click()
            time.sleep(CLICK_DELAY)
            clicks += 1

            # Log progress
            if clicks % 5 == 0:
                log(f'Clicked {clicks} times, captured {len(captured)} responses')

        log(f'Done clicking. Total clicks: {clicks}')

        # Extract venues from captured responses
        for data in captured:
            items = None
            if 'searchItems' in data:
                items = data['searchItems']
            elif 'Items' in data:
                items = data['Items']
            elif 'items' in data:
                items = data['items']

            if items:
                for item in items:
                    vid = f"foody-{item.get('Id', item.get('id', ''))}"
                    if vid not in seen_ids:
                        seen_ids.add(vid)

                        cuisines = []
                        raw = item.get('Cuisines') or item.get('LstCuisine') or []
                        if isinstance(raw, list):
                            cuisines = [c['Name'] if isinstance(c, dict) else str(c) for c in raw]

                        venues.append({
                            'id': vid,
                            'name': item.get('Name', ''),
                            'address': item.get('Address', ''),
                            'district': item.get('District', ''),
                            'city': 'TP.HCM',
                            'rating': item.get('AvgRating'),
                            'reviews': item.get('TotalReview') or item.get('TotalReviews'),
                            'cuisines': cuisines,
                            'lat': item.get('Latitude'),
                            'lng': item.get('Longitude'),
                            'source': 'foody',
                        })
                        new_count += 1

        log(f'Captured {len(captured)} API responses')
        log(f'New venues: +{new_count}')

    except Exception as e:
        log(f'Error: {e}')
    finally:
        page.close()
        context.close()

    return venues, new_count

def main():
    log('='*60)
    log('FOODY SCRAPER - PLAYWRIGHT (Click Button)')
    log('='*60)

    venues = load_existing()
    progress = load_progress()

    log(f'Existing venues: {len(venues)}')
    log(f'Last session: {progress.get("session", 0)}')

    new_total = 0

    with sync_playwright() as p:
        for session in range(progress.get('session', 0), MAX_CLICK_SESSIONS):
            log(f'\n--- Session {session + 1}/{MAX_CLICK_SESSIONS} ---')

            venues, new_count = scrape_with_button_click(p, venues)
            new_total += new_count

            progress = {
                'venues': venues,
                'session': session + 1,
                'clicks': progress.get('clicks', 0) + new_count,
            }
            save_progress(progress)
            save_venues(venues)

            if new_count == 0:
                log('No new venues, stopping')
                break

            if session < MAX_CLICK_SESSIONS - 1:
                time.sleep(3)

    log(f'\nDONE! +{new_total} new, {len(venues)} total')

if __name__ == '__main__':
    main()
