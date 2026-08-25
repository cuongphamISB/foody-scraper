#!/usr/bin/env python3
"""
Foody Scraper - Final Edition
Uses requests with fresh sessions for pagination
"""
import requests
import json
import time
import random
import sys
from pathlib import Path

OUTPUT_DIR = Path('data/foody-v2')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === CONFIG ===
PAGE_SIZE = 20
BASE_DELAY = 5  # Seconds between requests
SESSION_BATCH = 20  # Requests before longer cooldown
LONG_COOLDOWN = 60  # Seconds after every SESSION_BATCH requests
MAX_PAGES_PER_CITY = 500  # Safety limit per city
SAVE_EVERY = 20  # Save progress every N pages

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
        print(f'[{ts}] [unicode]')
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

def make_request(city_slug, page_num):
    """Make API request with fresh session"""
    # Fresh session each request
    session = requests.Session()

    params = {
        'ds': 'Restaurant',
        'page': page_num,
        'pageSize': PAGE_SIZE,
        'q': '',
        'Lat': 0,
        'Lon': 0,
        'vt': 'row',
        'st': 7,
        'append': 'false',
        't': int(time.time() * 1000),
    }

    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Referer': f'https://www.foody.vn/{city_slug}/o-dau',
        'X-Requested-With': 'XMLHttpRequest',
    }

    try:
        resp = session.get(
            'https://www.foody.vn/__get/Directory/IndexAsync',
            params=params,
            headers=headers,
            timeout=30
        )
        return resp
    except Exception as e:
        log(f'Request error: {e}', 'ERROR')
        return None

def main():
    log('=' * 60)
    log('FOODY SCRAPER - FINAL EDITION')
    log('=' * 60)

    venues, last_city, last_page = load_progress()
    seen_ids = {v['id'] for v in venues}

    log(f'Loaded: {len(venues)} venues')
    log(f'Position: city {last_city}, page {last_page}')

    session_total = 0
    pages_in_session = 0

    while last_city < len(CITIES):
        city_slug, city_id, city_name = CITIES[last_city]
        page = last_page

        log(f'\\n=== Scraping {city_name} ===')

        while page <= MAX_PAGES_PER_CITY:
            # Check skip
            skip_key = f'{city_slug}-{page}'
            if skip_key in seen_ids:
                page += 1
                continue

            log(f'{city_name} page {page}...', end=' ')

            resp = make_request(city_slug, page)

            if resp is None:
                log('Network error, waiting...')
                time.sleep(BASE_DELAY * 2)
                continue

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    items = data.get('searchItems', [])
                    total = data.get('totalResult', 0)

                    if not items:
                        log(f'No items - might be end')
                        break

                    new_count = 0
                    for item in items:
                        vid = f"foody-{item.get('Id', '')}"
                        if vid not in seen_ids:
                            seen_ids.add(vid)

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
                            new_count += 1

                    log(f'+{new_count} | Total: {len(venues)} | Available: {total}')

                    # Check if reached end
                    if page * PAGE_SIZE >= total:
                        log(f'Reached end of {city_name}: {total} venues')
                        break

                    # Check if getting empty responses (rate limit)
                    if new_count == 0:
                        log('No new items - possible rate limit')
                        time.sleep(BASE_DELAY * 3)

                except json.JSONDecodeError as e:
                    log(f'JSON error: {e}')

            elif resp.status_code == 429:
                log('RATE LIMITED!', 'RATE')
                log(f'Waiting {LONG_COOLDOWN * 2}s...')
                time.sleep(LONG_COOLDOWN * 2)

            else:
                log(f'HTTP {resp.status_code}')

            page += 1
            pages_in_session += 1
            session_total += 1

            # Save progress
            if page % SAVE_EVERY == 0:
                save_progress(venues, last_city, page)

            # Delay
            delay = BASE_DELAY + random.uniform(-1, 2)
            time.sleep(max(3, delay))

            # Longer cooldown every SESSION_BATCH requests
            if pages_in_session >= SESSION_BATCH:
                log(f'Session cooldown {LONG_COOLDOWN}s...')
                time.sleep(LONG_COOLDOWN)
                pages_in_session = 0

        # Move to next city
        last_city += 1
        last_page = 1
        save_progress(venues, last_city, last_page)

    # Final save
    output = OUTPUT_DIR / 'foody_v2.json'
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
