#!/usr/bin/env python3
"""
Foody Scraper - GitHub Actions Playwright Edition
Uses browser automation to scroll and get all venues
"""
import json
import time
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_FILE = Path('data/foody-batch/venues.json')
PROGRESS_FILE = Path('data/foody-batch/progress.json')
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Config - GitHub Actions timeout is 50 min, leave buffer
MAX_SCROLL_SESSIONS = 8  # ~5 min each = 40 min total
SCROLL_PAUSE = 2.0  # Seconds to wait after scroll
SCROLL_ITERATIONS = 25  # Scrolls per session

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'venues': [],
        'scrolled_count': 0,
        'session': 0,
    }

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

def scrape_with_scroll(p, venues):
    """Scroll through Foody page to load more venues"""
    seen_ids = {v['id'] for v in venues}
    new_count = 0

    # Create browser
    context = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage']
    ).new_context(
        viewport={'width': 1280, 'height': 800},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    )

    page = context.new_page()

    # Track captured venues from API
    captured = []

    def capture_response(response):
        if '__get/Directory/IndexAsync' in response.url or 'HomeListPlace' in response.url:
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
        # Navigate
        log('Navigating to Foody...')
        page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                 wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)

        # Get initial count
        initial_count = len(seen_ids)
        log(f'Initial venues loaded: {initial_count}')

        # Scroll to load more
        last_height = 0
        scroll_no_progress = 0

        for i in range(SCROLL_ITERATIONS):
            # Scroll down
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(SCROLL_PAUSE)

            new_height = page.evaluate('document.body.scrollHeight')

            if new_height == last_height:
                scroll_no_progress += 1
                if scroll_no_progress >= 3:
                    log(f'No more content after {i+1} scrolls')
                    break
            else:
                scroll_no_progress = 0

            last_height = new_height
            log(f'Scroll {i+1}/{SCROLL_ITERATIONS}: height={new_height}')

        # Extract venues from captured API responses
        for data in captured:
            items = None

            # Try different structures
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

                        # Extract cuisines
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
        log(f'New venues this session: +{new_count}')

    except Exception as e:
        log(f'Error: {e}')
    finally:
        page.close()
        context.close()

    return venues, new_count

def main():
    log('='*60)
    log('FOODY SCRAPER - PLAYWRIGHT (GitHub Actions)')
    log('='*60)

    # Load existing
    venues = load_existing()
    progress = load_progress()

    log(f'Existing venues: {len(venues)}')
    log(f'Last session: {progress.get("session", 0)}')

    new_total = 0

    with sync_playwright() as p:
        for session in range(progress.get('session', 0), MAX_SCROLL_SESSIONS):
            log(f'\\n--- Session {session + 1}/{MAX_SCROLL_SESSIONS} ---')

            venues, new_count = scrape_with_scroll(p, venues)
            new_total += new_count

            # Save progress
            progress = {
                'venues': venues,
                'session': session + 1,
                'scrolled_count': progress.get('scrolled_count', 0) + new_count,
            }
            save_progress(progress)
            save_venues(venues)

            if new_count == 0:
                log('No new venues, stopping')
                break

            # Small delay between sessions
            if session < MAX_SCROLL_SESSIONS - 1:
                time.sleep(3)

    log(f'\\nDONE! +{new_total} new, {len(venues)} total')

if __name__ == '__main__':
    main()
