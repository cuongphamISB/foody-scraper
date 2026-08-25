#!/usr/bin/env python3
"""
Foody Scraper - Playwright Edition
Uses browser to capture API responses with pagination
"""
from playwright.sync_api import sync_playwright
import json
import time
import random
import sys
from pathlib import Path

OUTPUT_DIR = Path('data/foody-playwright')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === CONFIG ===
PAGES_PER_SESSION = 50  # Pages per browser session
PAGE_DELAY = 3  # Delay between page navigations
SESSION_COOLDOWN = 120  # Seconds between sessions
MAX_RETRIES = 2

CITIES = [
    ('ho-chi-minh', 3, 'TP.HCM'),
    ('ha-noi', 1, 'Hanoi'),
    ('da-nang', 2, 'Da Nang'),
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
]

def log(msg):
    ts = time.strftime('%H:%M:%S')
    try:
        print(f'[{ts}] {msg}')
    except:
        print(f'[{ts}] [content]')
    sys.stdout.flush()

def load_progress():
    f = OUTPUT_DIR / 'progress.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return (data.get('venues', []),
                   data.get('last_city', 0),
                   data.get('last_page', 0))
    return [], 0, 1

def save_progress(venues, last_city, last_page):
    f = OUTPUT_DIR / 'progress.json'
    with open(f, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'last_city': last_city,
            'last_page': last_page,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False)

def scrape_with_browser(p, venues, seen_ids, city_slug, city_name, start_page, total_pages):
    """Scrape pages using Playwright browser"""
    log(f'Starting browser session for {city_name}, page {start_page}')

    captured_venues = []

    # Create context with anti-detection
    context = p.chromium.launch(
        headless=True,
        args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
    ).new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent=random.choice(USER_AGENTS),
    )

    # Stealth scripts
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)

    page = context.new_page()

    for page_num in range(start_page, start_page + total_pages):
        log(f'Page {page_num}...')

        responses = []

        def on_response(response):
            if 'IndexAsync' in response.url:
                try:
                    body = response.body()
                    if body.startswith(b'{'):
                        data = json.loads(body)
                        responses.append(data)
                except:
                    pass

        page.on('response', on_response)

        try:
            # Navigate
            page.goto(
                f'https://www.foody.vn/{city_slug}/o-dau?page={page_num}',
                wait_until='domcontentloaded',
                timeout=60000
            )
            page.wait_for_timeout(random.uniform(2, 4))

            # Scroll a bit for natural behavior
            for _ in range(random.randint(2, 4)):
                page.evaluate('window.scrollBy(0, 200)')
                time.sleep(random.uniform(0.2, 0.5))

            # Process captured responses
            if responses:
                data = responses[-1]
                items = data.get('searchItems', [])
                total = data.get('totalResult', 0)

                if items:
                    new_count = 0
                    for item in items:
                        vid = f"foody-{item.get('Id', '')}"
                        if vid not in seen_ids:
                            seen_ids.add(vid)
                            new_count += 1

                            cuisines = []
                            if isinstance(item.get('Cuisines'), list):
                                cuisines = [c.get('Name', '') if isinstance(c, dict) else str(c)
                                          for c in item['Cuisines']]

                            venues.append({
                                'id': vid,
                                'name': item.get('Name', ''),
                                'address': item.get('Address', ''),
                                'district': item.get('District', ''),
                                'city': city_name,
                                'rating': item.get('AvgRating'),
                                'reviews': item.get('TotalReview'),
                                'cuisines': cuisines,
                                'lat': item.get('Latitude'),
                                'lng': item.get('Longitude'),
                                'source': 'foody',
                            })
                            captured_venues.append(vid)

                    log(f'  +{new_count} new | Total: {len(venues)} | Available: {total}')

                    # Check if reached end
                    if page_num * 20 >= total:
                        log(f'Reached end: {total} venues')
                        break
                else:
                    log(f'  No items returned')
            else:
                log(f'  No API response captured')

        except Exception as e:
            log(f'Error: {e}')

        # Delay between pages
        delay = PAGE_DELAY + random.uniform(-1, 2)
        time.sleep(max(2, delay))

        # Save progress periodically
        if page_num % 10 == 0:
            save_progress(venues, CITIES.index((city_slug, None, city_name)), page_num)

    page.close()
    context.close()

    return len(captured_venues)

def main():
    log('=' * 60)
    log('FOODY SCRAPER - PLAYWRIGHT EDITION')
    log('=' * 60)

    venues, last_city, last_page = load_progress()
    seen_ids = {v['id'] for v in venues}

    log(f'Loaded: {len(venues)} venues')
    log(f'Position: city {last_city}, page {last_page}')

    session_num = 1

    with sync_playwright() as p:
        while last_city < len(CITIES):
            city_slug, city_id, city_name = CITIES[last_city]

            log(f'\\n=== Scraping {city_name} from page {last_page} ===')

            # Scrape batch of pages
            pages_scraped = scrape_with_browser(
                p, venues, seen_ids,
                city_slug, city_name,
                last_page, PAGES_PER_SESSION
            )

            if pages_scraped == 0:
                log('No pages scraped, trying again after cooldown')
                time.sleep(SESSION_COOLDOWN)
            else:
                # Move to next city or continue
                last_page += PAGES_PER_SESSION

                # Check if done with this city
                # For now, just continue
                if last_page > 1000:  # Safety limit per city
                    log(f'Done with {city_name} (page {last_page})')
                    last_city += 1
                    last_page = 1

            save_progress(venues, last_city, last_page)

            # Cooldown
            log(f'Session cooldown {SESSION_COOLDOWN}s...')
            time.sleep(SESSION_COOLDOWN)

            session_num += 1

            # Safety
            if session_num > 500:
                log('Safety limit')
                break

    # Final save
    output = OUTPUT_DIR / 'foody_playwright.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'source': 'foody.vn',
            'completed_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

    log(f'\\n{"="*60}')
    log(f'DONE! {len(venues)} venues')
    log(f'Saved: {output}')

if __name__ == '__main__':
    main()
