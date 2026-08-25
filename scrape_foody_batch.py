#!/usr/bin/env python3
"""
Foody Scraper - Batch Edition
Gets ~800 venues per run, saves to file
"""
import json
import time
import random
import sys
import requests
from pathlib import Path

OUTPUT_DIR = Path('data/foody-batch')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PAGE_SIZE = 200
DELAY = 2  # seconds between requests

def log(msg):
    ts = time.strftime('%H:%M:%S')
    try:
        print(f'[{ts}] {msg}')
    except:
        print(f'[{ts}] [unicode]')
    sys.stdout.flush()

def load_progress():
    f = OUTPUT_DIR / 'venues.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('venues', [])
    return []

def save_venues(venues):
    f = OUTPUT_DIR / 'venues.json'
    with open(f, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)
    log(f'Saved {len(venues)} venues')

def scrape_batch():
    venues = load_progress()
    seen_ids = {v['id'] for v in venues}

    log(f'Starting batch. Current: {len(venues)} venues')

    for page in range(1, 11):
        session = requests.Session()
        session.headers.update({
            'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/{random.randint(120,127)}.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://www.foody.vn/ho-chi-minh/o-dau',
            'X-Requested-With': 'XMLHttpRequest',
        })

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

        print(f'Page {page}...', end=' ', flush=True)

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
                            'city': 'TP.HCM',
                            'rating': item.get('AvgRating'),
                            'reviews': item.get('TotalReview'),
                            'cuisines': cuisines,
                            'lat': item.get('Latitude'),
                            'lng': item.get('Longitude'),
                            'source': 'foody',
                        })
                        new_count += 1

                log(f'+{new_count} new, total: {len(venues)}, available: {total}')

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
    log(f'Batch complete: {len(venues)} total venues')

    return venues

if __name__ == '__main__':
    scrape_batch()
