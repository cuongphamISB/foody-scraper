#!/usr/bin/env python3
"""
Foody Scraper - Continuous Edition
Chạy nhiều lần, mỗi lần được ~800 venues
Cần thay đổi network/reset rate limit giữa các lần chạy
"""
import json
import time
import sys
import requests
from pathlib import Path

OUTPUT_DIR = Path('data/foody-batch')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / 'venues.json'
PROGRESS_FILE = OUTPUT_DIR / 'progress.json'

PAGE_SIZE = 200
DELAY = 2

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def load_progress():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('venues', [])
    return []

def load_meta():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'runs': 0, 'last_run': None}

def save_venues(venues):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)
    log(f'Saved {len(venues)} venues')

def save_meta(meta):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

def scrape_batch():
    venues = load_progress()
    seen_ids = {v['id'] for v in venues}

    meta = load_meta()
    meta['runs'] += 1
    meta['last_run'] = time.strftime('%Y-%m-%d %H:%M:%S')

    log(f'Starting batch #{meta["runs"]}. Current: {len(venues)} venues')

    # Fresh session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': 'https://www.foody.vn/ho-chi-minh/o-dau',
        'X-Requested-With': 'XMLHttpRequest',
    })

    # Get cookies
    session.get('https://www.foody.vn/ho-chi-minh', timeout=30)
    log(f'Session ID: {session.cookies.get("__ondemand_sessionid", "N/A")}')

    new_count = 0

    for page in range(1, 11):
        params = {
            'ds': 'Restaurant',
            'page': page,
            'pageSize': PAGE_SIZE,
            'q': '',
            'Lat': 0,
            'Lon': 0,
            'vt': 'row',
            'st': 7,
            'append': 'false',
            't': int(time.time() * 1000),
        }

        log(f'Page {page}...', end=' ')

        try:
            resp = session.get(
                'https://www.foody.vn/__get/Directory/IndexAsync',
                params=params,
                timeout=30
            )

            if resp.status_code == 200:
                data = resp.json()
                items = data.get('searchItems', [])
                total = data.get('totalResult', 0)

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
                            'city': 'TP.HCM',
                            'rating': item.get('AvgRating'),
                            'reviews': item.get('TotalReview'),
                            'cuisines': cuisines,
                            'lat': item.get('Latitude'),
                            'lng': item.get('Longitude'),
                            'source': 'foody',
                            'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        })
                        new_count += 1

                log(f'+{len(items)} new, total: {len(venues)}, available: {total}')

                if total == 0:
                    log('Rate limit reached')
                    break
            else:
                log(f'HTTP {resp.status_code}')

        except Exception as e:
            log(f'Error: {e}')

        if page < 10:
            time.sleep(DELAY)

    save_venues(venues)
    save_meta(meta)

    log(f'Batch complete: +{new_count} new venues, {len(venues)} total')

    return venues

if __name__ == '__main__':
    scrape_batch()
