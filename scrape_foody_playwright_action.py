#!/usr/bin/env python3
"""
Foody Scraper - Fixed to parse Items as JSON string
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_FILE = Path('data/foody-batch/venues.json')
PROGRESS_FILE = Path('data/foody-batch/progress.json')

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

def scrape(p, venues):
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
        # Only capture HomeListPlace endpoint
        if 'HomeListPlace' in response.url:
            try:
                body = response.body()
                if body:
                    text = body.decode('utf-8', errors='ignore')
                    if text.strip().startswith('{'):
                        captured.append(text)
            except:
                pass

    page.on('response', capture_response)

    try:
        log('Navigating...')
        page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                 wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)

        clicks = 0
        max_clicks = 60  # More clicks = more venues

        while clicks < max_clicks:
            button = None
            for sel in ['button:has-text("Xem thêm")', 'a:has-text("Xem thêm")', '[class*="more"]']:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        button = btn
                        break
                except:
                    pass

            if not button:
                log(f'No more button after {clicks} clicks')
                break

            button.click()
            clicks += 1
            time.sleep(2)

            if clicks % 5 == 0:
                log(f'Clicks: {clicks}, captured: {len(captured)}')

        log(f'Done. {clicks} clicks, {len(captured)} responses')

        # Parse captured data
        for text in captured:
            try:
                data = json.loads(text)
                items_raw = data.get('Items', [])

                # Items is a JSON string, parse it
                if isinstance(items_raw, str):
                    items = json.loads(items_raw)
                else:
                    items = items_raw

                if isinstance(items, list):
                    for item in items:
                        vid = f"foody-{item.get('Id', item.get('id', ''))}"
                        if vid not in seen_ids:
                            seen_ids.add(vid)

                            cuisines = []
                            raw = item.get('LstCuisine') or []
                            if isinstance(raw, list):
                                cuisines = [c['Name'] if isinstance(c, dict) else str(c) for c in raw]

                            venues.append({
                                'id': vid,
                                'name': item.get('Name', ''),
                                'address': item.get('Address', ''),
                                'district': item.get('District', ''),
                                'city': 'TP.HCM',
                                'rating': item.get('AvgRating'),
                                'reviews': item.get('TotalReviews'),
                                'cuisines': cuisines,
                                'lat': item.get('Latitude'),
                                'lng': item.get('Longitude'),
                                'source': 'foody',
                            })
                            new_count += 1

            except Exception as e:
                log(f'Parse error: {e}')

        log(f'New venues: +{new_count}')

    except Exception as e:
        log(f'Error: {e}')
    finally:
        page.close()
        context.close()

    return venues, new_count

def main():
    log('='*50)
    log('FOODY SCRAPER - Fixed JSON parse')
    log('='*50)

    venues = load_existing()
    progress = load_progress()
    log(f'Existing: {len(venues)}, session: {progress.get("session", 0)}')

    with sync_playwright() as p:
        venues, new_count = scrape(p, venues)

    save_venues(venues)
    save_progress({'session': progress.get('session', 0) + 1})
    log(f'DONE! Total: {len(venues)}, new: +{new_count}')

if __name__ == '__main__':
    main()
