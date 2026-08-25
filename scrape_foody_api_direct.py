#!/usr/bin/env python3
"""
Foody Scraper - Direct API Edition
Uses requests library with realistic delays
"""
import json
import time
import random
import requests
import sys
from pathlib import Path
from urllib.parse import urlencode

OUTPUT_DIR = Path('data/foody-api')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === CONFIG ===
PAGE_SIZE = 20
BASE_DELAY = 8  # Base delay between requests
MAX_DELAY = 20  # Max random delay
SESSION_COOLDOWN = 180  # 3 min between sessions
RATE_LIMIT_WAIT = 600  # 10 min when rate limited
BATCH_SAVE = 50  # Save progress every N pages
MAX_CONSECUTIVE_FAILS = 5
CITIES = [
    ('ho-chi-minh', 3, 'TP.HCM'),
    ('ha-noi', 1, 'Hanoi'),
    ('da-nang', 2, 'Da Nang'),
]

# User agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
]

def log(msg, level='INFO'):
    ts = time.strftime('%H:%M:%S')
    prefix = {'INFO': '', 'WARN': '[WARN]', 'ERROR': '[ERROR]', 'RATE': '[RATE]'}.get(level, '')
    try:
        print(f'[{ts}] {prefix} {msg}')
    except:
        print(f'[{ts}] {prefix} [unicode content]')
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
                   data.get('rate_limited', False),
                   data.get('consecutive_fails', 0))
    return [], 0, 1, {}, False, 0

def save_progress(venues, last_city, last_page, failed_pages, rate_limited, consecutive_fails):
    f = OUTPUT_DIR / 'progress.json'
    with open(f, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'last_city': last_city,
            'last_page': last_page,
            'failed_pages': failed_pages,
            'rate_limited': rate_limited,
            'consecutive_fails': consecutive_fails,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False)

def make_request(city_slug, page_num, session):
    """Make API request with error handling"""
    url = 'https://www.foody.vn/__get/Directory/IndexAsync'
    params = {
        'ds': 'Restaurant',
        'page': page_num,
        'pageSize': PAGE_SIZE,
        'q': '',
    }
    # Add timestamp
    params['t'] = int(time.time() * 1000)

    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': f'https://www.foody.vn/{city_slug}/o-dau',
        'X-Requested-With': 'XMLHttpRequest',
        'Connection': 'keep-alive',
    }

    try:
        resp = session.get(url, params=params, headers=headers, timeout=30)
        return resp
    except requests.exceptions.Timeout:
        log(f'Request timeout', 'WARN')
        return None
    except requests.exceptions.RequestException as e:
        log(f'Request error: {e}', 'WARN')
        return None

def scrape_city(session, city_idx, city_slug, city_name, start_page, venues, seen_ids):
    """Scrape one city"""
    page = start_page
    pages_ok = 0

    while True:
        # Check skip condition
        skip_key = f'{city_idx}-{page}'
        if skip_key in seen_ids.get('failed', {}):
            fails = seen_ids['failed'][skip_key]
            if fails >= 3:
                log(f'City {city_name} page {page}: SKIP (failed {fails}x)')
                page += 1
                continue

        log(f'City {city_name} page {page}...')
        resp = make_request(city_slug, page, session)

        if resp is None:
            # Network error
            delay = BASE_DELAY * random.uniform(1, 2)
            log(f'Network error, waiting {delay:.0f}s...', 'WARN')
            time.sleep(delay)
            continue

        if resp.status_code == 200:
            try:
                data = resp.json()

                if 'searchItems' in data:
                    items = data['searchItems']
                    total = data.get('totalResult', 0)

                    if not items:
                        log(f'No items on page {page}, might be end of data')
                        break

                    new_count = 0
                    for item in items:
                        vid = f"foody-{item.get('Id', '')}"
                        if vid not in seen_ids['ids']:
                            seen_ids['ids'].add(vid)
                            new_count += 1

                            # Extract cuisines
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

                    log(f'  +{new_count} new | Total: {len(venues)} | Total available: {total}')
                    pages_ok += 1

                    # Check if we've reached the end
                    if page * PAGE_SIZE >= total:
                        log(f'Reached end of {city_name}: {total} venues')
                        break

                elif 'error' in data or 'ErrorMessage' in data:
                    err = data.get('error', data.get('ErrorMessage', 'Unknown'))
                    log(f'API error: {err}', 'ERROR')
                    if 'rate' in str(err).lower() or 'limit' in str(err).lower():
                        return pages_ok, True  # Rate limited
                    break

            except json.JSONDecodeError as e:
                log(f'JSON parse error: {e}', 'WARN')

        elif resp.status_code == 429:
            log(f'Rate limited! (HTTP 429)', 'RATE')
            return pages_ok, True

        elif resp.status_code == 403:
            log(f'Forbidden! (HTTP 403)', 'RATE')
            return pages_ok, True

        else:
            log(f'HTTP {resp.status_code}', 'WARN')
            if resp.status_code >= 500:
                # Server error, might recover
                pass

        # Delay between requests
        delay = BASE_DELAY + random.uniform(-2, MAX_DELAY - BASE_DELAY)
        log(f'Delay {delay:.1f}s...')
        time.sleep(max(5, delay))

        page += 1

        # Save progress periodically
        if pages_ok > 0 and pages_ok % BATCH_SAVE == 0:
            save_progress(venues, city_idx, page, seen_ids.get('failed', {}), False, 0)

    return pages_ok, False

def main():
    log('=' * 60)
    log('FOODY SCRAPER - DIRECT API')
    log('=' * 60)

    venues, last_city, last_page, failed_pages, rate_limited, consecutive_fails = load_progress()
    seen_ids = {'ids': {v['id'] for v in venues}, 'failed': failed_pages}

    log(f'Loaded: {len(venues)} venues')
    log(f'Position: city {last_city}, page {last_page}')
    log(f'Failed pages: {len(failed_pages)}')

    session_num = 1
    total_venues = len(venues)

    while True:
        log(f'\\n--- Session {session_num} ---')

        # Create session with retry adapter
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            max_retries=1,
            pool_connections=1,
            pool_maxsize=1,
        )
        session.mount('https://www.foody.vn', adapter)

        city_idx = last_city
        while city_idx < len(CITIES):
            city_slug, city_id, city_name = CITIES[city_idx]

            # Check if rate limited
            if rate_limited:
                log(f'Rate limited! Waiting {RATE_LIMIT_WAIT}s...', 'RATE')
                time.sleep(RATE_LIMIT_WAIT)
                rate_limited = False

            start_page = last_page if city_idx == last_city else 1

            log(f'=== Scraping {city_name} from page {start_page} ===')
            pages_ok, rl = scrape_city(
                session, city_idx, city_slug, city_name,
                start_page, venues, seen_ids
            )

            if rl:
                rate_limited = True
                save_progress(venues, city_idx, start_page, seen_ids['failed'], True, consecutive_fails)
                break

            if pages_ok == 0:
                consecutive_fails += 1
                if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    log(f'Too many consecutive fails ({consecutive_fails}). Pausing...', 'ERROR')
                    time.sleep(RATE_LIMIT_WAIT)
                    consecutive_fails = 0
            else:
                consecutive_fails = 0

            last_page = 1  # Reset for next city
            city_idx += 1
            save_progress(venues, city_idx, 1, seen_ids['failed'], False, consecutive_fails)

        # Cooldown between sessions
        if city_idx >= len(CITIES):
            log('All cities completed!')
            break

        new_venues = len(venues) - total_venues
        log(f'Session {session_num}: +{new_venues} venues')
        total_venues = len(venues)

        if not rate_limited:
            log(f'Session cooldown {SESSION_COOLDOWN}s...')
            time.sleep(SESSION_COOLDOWN)

        session_num += 1

        # Safety limit
        if session_num > 1000:
            log('Safety limit (1000 sessions)')
            break

        # Backup
        if session_num % 100 == 0:
            backup = OUTPUT_DIR / f'backup_{session_num}.json'
            with open(backup, 'w', encoding='utf-8') as f:
                json.dump({'venues': venues, 'total': len(venues)}, f, ensure_ascii=False)
            log(f'Backup: {backup}')

    # Final save
    output = OUTPUT_DIR / 'foody_api.json'
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
