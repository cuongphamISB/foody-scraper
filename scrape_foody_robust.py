#!/usr/bin/env python3
"""
Foody Scraper - Robust Overnight Edition
- Realistic user behavior simulation
- Multiple anti-detection techniques
- Exponential backoff for rate limits
- Session rotation
- Progress saved continuously
"""
import json
import time
import random
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-robust')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === CONFIG ===
BATCH_SIZE = 30  # Smaller batches to look more natural
BASE_DELAY = 15  # Base delay between pages (seconds)
MAX_DELAY = 45  # Max random delay
SESSION_PAGES = 20  # Pages per session before restart
SESSION_COOLDOWN = 300  # 5 min cooldown between sessions
RATE_LIMIT_COOLDOWN = 600  # 10 min when rate limited
MAX_RETRIES = 3
SKIP_AFTER_FAILS = 3
CITIES = [
    ('ho-chi-minh', 3, 'TP.HCM'),
    ('ha-noi', 1, 'Hanoi'),
]

def log(msg, level='INFO'):
    ts = time.strftime('%H:%M:%S')
    prefix = {'INFO': '', 'WARN': '[WARN]', 'ERROR': '[ERROR]', 'RATE': '[RATE]'}.get(level, '')
    print(f'[{ts}] {prefix} {msg}')
    sys.stdout.flush()

def load_progress():
    f = OUTPUT_DIR / 'progress.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return (data.get('venues', []),
                   data.get('last_city', 0),
                   data.get('last_page', 0),
                   data.get('failed_pages', {}),
                   data.get('rate_limited', False))
    return [], 0, 0, {}, False

def save_progress(venues, last_city, last_page, failed_pages, rate_limited):
    f = OUTPUT_DIR / 'progress.json'
    with open(f, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'last_city': last_city,
            'last_page': last_page,
            'failed_pages': failed_pages,
            'rate_limited': rate_limited,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False)

def simulate_user_behavior(page):
    """Simulate realistic user browsing patterns"""
    try:
        # Random scroll patterns
        scroll_positions = [0, 200, 400, 200, 0, random.randint(100, 500)]
        for pos in scroll_positions:
            page.evaluate(f'window.scrollTo(0, {pos})')
            time.sleep(random.uniform(0.3, 0.8))

        # Occasional mouse movements
        for _ in range(random.randint(2, 5)):
            x = random.randint(100, 800)
            y = random.randint(200, 600)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.1, 0.3))

        # Hover over a random element occasionally
        if random.random() > 0.7:
            try:
                elements = page.query_selector_all('.res-item, .restaurant-item, [class*="item"]')
                if elements:
                    elem = random.choice(elements)
                    elem.hover()
                    time.sleep(random.uniform(0.5, 1.5))
            except:
                pass
    except Exception as e:
        log(f'Behavior simulation error: {e}', 'WARN')

def check_rate_limit(page):
    """Check if page shows rate limit message"""
    try:
        # Check for common rate limit indicators
        text = page.inner_text('body').lower()
        if any(x in text for x in ['rate limit', 'quá nhanh', 'too many', 'blocked', 'vui lòng đợi', 'please wait']):
            return True
        # Check page title
        title = page.title().lower()
        if 'rate limit' in title or 'blocked' in title:
            return True
    except:
        pass
    return False

def scrape_page(page, city_slug, city_id, page_num):
    """Scrape one page with retry logic"""
    responses = []

    # Set up response interceptor
    def on_response(response):
        url = response.url
        if 'IndexAsync' in url or 'GetItems' in url:
            try:
                body = response.body()
                if body and body.startswith(b'{'):
                    responses.append(json.loads(body))
            except:
                pass

    page.on('response', on_response)

    # Navigate with realistic behavior
    try:
        # First go to city page
        url = f'https://www.foody.vn/{city_slug}/o-dau'
        log(f'Navigating to {url}')

        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(random.uniform(2, 4))

        # Simulate user looking at page
        simulate_user_behavior(page)

        # Check for rate limit immediately
        if check_rate_limit(page):
            return None, True  # (data, is_rate_limit)

        # Now navigate with pagination
        # Try to click next page or construct URL
        page.goto(
            f'{url}?page={page_num}',
            wait_until='domcontentloaded',
            timeout=60000
        )
        page.wait_for_timeout(random.uniform(1.5, 3))

        # Simulate more user behavior
        simulate_user_behavior(page)

        if check_rate_limit(page):
            return None, True

    except Exception as e:
        log(f'Navigation error: {e}', 'WARN')
        return None, False

    return responses[0] if responses else None, False

def create_stealth_context(p):
    """Create a stealth browser context"""
    # Realistic user agents
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    ]

    # Random viewport
    viewports = [
        {'width': 1920, 'height': 1080},
        {'width': 1366, 'height': 768},
        {'width': 1536, 'height': 864},
    ]

    # Random locale
    locales = ['en-US,en;q=0.9', 'vi-VN,vi;q=0.9,en;q=0.8', 'en-GB,en;q=0.9']

    context = p.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
        ]
    ).new_context(
        viewport=random.choice(viewports),
        locale=random.choice(locales),
        user_agent=random.choice(user_agents),
    )

    # Inject stealth scripts
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en', 'vi']
        });
    """)

    return context

def run_session(p, venues, start_city_idx, start_page, failed_pages, rate_limited):
    """Run one scraping session"""
    log(f'=== Starting session at city {start_city_idx}, page {start_page + 1} ===')

    # Create fresh context
    context = create_stealth_context(p)
    page = context.new_page()

    seen_ids = {v['id'] for v in venues}
    pages_in_session = 0
    session_rate_limited = rate_limited

    city_idx = start_city_idx
    while city_idx < len(CITIES):
        city_slug, city_id, city_name = CITIES[city_idx]
        log(f'Processing city: {city_name}')

        # Start page for this city
        if city_idx == start_city_idx:
            page_start = start_page + 1
        else:
            page_start = 1

        for page_num in range(page_start, 1000):  # High limit
            # Check skip condition
            skip_key = f'{city_idx}-{page_num}'
            if failed_pages.get(skip_key, 0) >= SKIP_AFTER_FAILS:
                log(f'Page {page_num}: SKIPPED (failed {failed_pages[skip_key]}x)')
                continue

            # Check rate limit
            if session_rate_limited:
                log('Still rate limited, ending session early')
                break

            start = time.time()
            success = False
            is_rate_limit = False

            for attempt in range(MAX_RETRIES):
                data, is_rl = scrape_page(page, city_slug, city_id, page_num)
                is_rate_limit = is_rl

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    wait = BASE_DELAY * (2 ** attempt) * 2
                    log(f'Rate limited, waiting {wait}s before retry...', 'RATE')
                    time.sleep(wait)
                    continue

                if data and isinstance(data, dict):
                    # Try different data structures
                    items = None
                    if 'searchItems' in data:
                        items = data['searchItems']
                    elif 'items' in data:
                        items = data['items']
                    elif 'd' in data:
                        items = data.get('d', {}).get('items', [])

                    if items:
                        new_count = 0
                        for item in items:
                            vid = f"foody-{item.get('Id', item.get('id', ''))}"
                            if vid not in seen_ids:
                                seen_ids.add(vid)
                                new_count += 1

                                # Extract cuisines safely
                                cuisines = []
                                if isinstance(item.get('Cuisines'), list):
                                    cuisines = [c['Name'] if isinstance(c, dict) else str(c)
                                               for c in item['Cuisines']]

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
                                    'source': 'foody',
                                    'city': city_name,
                                })

                        elapsed = time.time() - start
                        log(f'Page {page_num}: {len(items)} items (+{new_count}) | {len(venues)} total | {elapsed:.1f}s')
                        save_progress(venues, city_idx, page_num, failed_pages, session_rate_limited)

                        # Reset fail count
                        if skip_key in failed_pages:
                            del failed_pages[skip_key]

                        success = True
                        pages_in_session += 1
                        break

                elif attempt < MAX_RETRIES - 1 and not is_rate_limit:
                    wait = BASE_DELAY * (2 ** attempt)
                    log(f'Retry {attempt + 1} failed, waiting {wait}s...', 'WARN')
                    time.sleep(wait)

            if not success:
                if is_rate_limit:
                    log(f'Page {page_num}: RATE LIMITED', 'RATE')
                    session_rate_limited = True
                    failed_pages[skip_key] = failed_pages.get(skip_key, 0) + 2  # Bigger penalty
                    save_progress(venues, city_idx, page_num, failed_pages, True)
                    break
                else:
                    log(f'Page {page_num}: FAILED')
                    failed_pages[skip_key] = failed_pages.get(skip_key, 0) + 1
                    save_progress(venues, city_idx, page_num, failed_pages, session_rate_limited)

            # Delay between pages - longer for better survival
            delay = BASE_DELAY + random.uniform(-5, MAX_DELAY - BASE_DELAY)
            log(f'Delay {delay:.1f}s...')
            time.sleep(max(BASE_DELAY, delay))

            # Check if session is getting long
            if pages_in_session >= SESSION_PAGES:
                log(f'Session limit reached ({SESSION_PAGES} pages)')
                break

        # Move to next city
        if session_rate_limited:
            break
        city_idx += 1
        start_page = 0  # Reset for new city

    page.close()
    context.close()

    return venues, city_idx, start_page if city_idx < len(CITIES) else 0, failed_pages, session_rate_limited, pages_in_session

def main():
    log('=' * 60)
    log('FOODY SCRAPER - ROBUST OVERNIGHT')
    log('=' * 60)

    venues, last_city, last_page, failed_pages, rate_limited = load_progress()
    log(f'Loaded: {len(venues)} venues')
    log(f'Last position: city {last_city}, page {last_page}')
    log(f'Failed pages: {len(failed_pages)}')
    log(f'Rate limited: {rate_limited}')

    session_num = 1
    consecutive_empty = 0

    with sync_playwright() as p:
        while True:
            log(f'\\n--- Session {session_num} ---')

            # If rate limited, longer cooldown
            cooldown = RATE_LIMIT_COOLDOWN if rate_limited else SESSION_COOLDOWN

            # If no progress, increase cooldown
            if rate_limited:
                log(f'Rate limited! Waiting {cooldown}s before retry...', 'RATE')
                time.sleep(cooldown)
                rate_limited = False  # Reset to try again
            else:
                # Normal session
                new_venues, new_city, new_page, new_failed, rl, pages_ok = run_session(
                    p, venues, last_city, last_page, failed_pages, rate_limited
                )

                venues = new_venues
                last_city = new_city
                last_page = new_page
                failed_pages = new_failed
                rate_limited = rl

                if pages_ok > 0:
                    consecutive_empty = 0
                    log(f'Session {session_num}: {pages_ok} pages OK')
                else:
                    consecutive_empty += 1
                    log(f'Session {session_num}: No pages scraped', 'WARN')

                # Check completion
                if last_city >= len(CITIES):
                    log('All cities completed!')
                    break

                # Cooldown between sessions
                if pages_ok > 0:
                    log(f'Cooldown {cooldown}s...')
                    time.sleep(cooldown)
                else:
                    # Longer wait on failure
                    log(f'Longer cooldown {cooldown * 2}s due to no progress...')
                    time.sleep(cooldown * 2)

            session_num += 1

            # Safety limit
            if session_num > 500:
                log('Safety limit (500 sessions) reached')
                break

            # Save backup every 50 sessions
            if session_num % 50 == 0:
                backup = OUTPUT_DIR / f'backup_{session_num}.json'
                with open(backup, 'w', encoding='utf-8') as f:
                    json.dump({
                        'venues': venues,
                        'total': len(venues),
                        'last_city': last_city,
                        'last_page': last_page,
                    }, f, ensure_ascii=False)
                log(f'Backup saved: {backup}')

    # Final save
    output = OUTPUT_DIR / 'foody_robust.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'source': 'foody.vn',
            'completed_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

    log(f'\\n{"="*60}')
    log(f'DONE! {len(venues)} venues scraped')
    log(f'Saved: {output}')

if __name__ == '__main__':
    main()
