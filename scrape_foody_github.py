#!/usr/bin/env python3
"""
Foody Scraper - Complete Rewrite
Uses all 7 st (sort) values to maximize venues per session
"""
import json
import time
import random
import sys
import requests
from pathlib import Path

OUTPUT_FILE = Path('data/foody-batch/venues.json')
PROGRESS_FILE = Path('data/foody-batch/progress.json')

# Config
ST_VALUES = [1, 2, 3, 4, 5, 6, 7]
PAGE_SIZE = 50
MAX_PAGES_PER_ST = 4
API_DELAY = 1.5

# HCM Districts
DISTRICTS = [
    (1, 'Quận 1'), (2, 'Quận 2'), (3, 'Quận 3'), (4, 'Quận 4'),
    (5, 'Quận 5'), (6, 'Quận 6'), (7, 'Quận 7'), (8, 'Quận 8'),
    (9, 'Quận 9'), (10, 'Quận 10'), (11, 'Quận 11'), (12, 'Quận 12'),
    (16, 'Bình Thạnh'), (17, 'Gò Vấp'), (18, 'Tân Bình'), (19, 'Tân Phú'),
    (20, 'Phú Nhuận'), (21, 'Thủ Đức'), (24, 'Bình Tân'),
    (22, 'Bình Chánh'), (25, 'Củ Chi'), (26, 'Hóc Môn'),
    (27, 'Nhà Bè'), (28, 'Cần Giờ'),
]

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'venues': [],
        'completed_districts': [],
        'district_pages': {},
        'total_runs': 0,
        'last_run': None
    }

def save_progress(data):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def load_existing():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get('venues', [])
    return []

def save_venues(venues):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

def fetch_api(district_id, st, page):
    """Fetch one page via HTTP API"""
    url = (
        f'https://www.foody.vn/ho-chi-minh/food/dia-diem'
        f'?ds=Restaurant&vt=row&st={st}&provinceId=217'
        f'&dt={district_id}&page={page}&pageSize={PAGE_SIZE}'
        f'&t={int(time.time() * 1000)}'
    )

    headers = {
        'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/{random.randint(120,127)}.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json',
        'Accept-Language': 'vi-VN,vi;q=0.9',
        'Referer': 'https://www.foody.vn/ho-chi-minh',
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        log(f'API error: {e}')
    return None

def scrape_district_http(district_id, district_name, seen_ids):
    """Scrape one district using HTTP API with all st values"""
    venues = []
    new_count = 0
    api_calls = 0

    log(f'Scraping {district_name} (id={district_id})')

    for st in ST_VALUES:
        for page in range(1, MAX_PAGES_PER_ST + 1):
            data = fetch_api(district_id, st, page)
            api_calls += 1

            if not data:
                break

            items = data.get('searchItems', [])
            total = data.get('totalResult', 0)

            if not items:
                break

            for item in items:
                vid = f"foody-{item.get('Id', '')}"
                if vid not in seen_ids:
                    seen_ids.add(vid)

                    cuisines = []
                    for c in item.get('Cuisines', []) or []:
                        if isinstance(c, dict):
                            cuisines.append(c.get('Name', ''))

                    venues.append({
                        'id': vid,
                        'name': item.get('Name', ''),
                        'address': item.get('Address', ''),
                        'district': item.get('District', district_name),
                        'city': 'TP.HCM',
                        'rating': item.get('AvgRating'),
                        'reviews': item.get('TotalReview'),
                        'cuisines': cuisines,
                        'lat': item.get('Latitude'),
                        'lng': item.get('Longitude'),
                        'source': 'foody',
                    })
                    new_count += 1

            time.sleep(API_DELAY)

    log(f'  {district_name}: +{new_count} new ({len(venues)} total) | {api_calls} API calls')
    return venues

def main():
    log('=' * 60)
    log('FOODY SCRAPER - Complete Rewrite')
    log('Strategy: All 7 st values x 4 pages = max coverage')
    log('=' * 60)

    existing_venues = load_existing()
    seen_ids = {v['id'] for v in existing_venues}
    all_venues = existing_venues.copy()

    log(f'Existing venues: {len(all_venues)}')

    progress = load_progress()
    completed = progress.get('completed_districts', [])

    log(f'Completed districts: {len(completed)}/{len(DISTRICTS)}')

    # Scrape multiple districts per run
    districts_per_run = 15  # Estimate: 15 districts × 2 min = 30 min
    districts_scraped = 0

    start_time = time.time()

    for dist_id, dist_name in DISTRICTS:
        if dist_id in completed:
            continue

        # Check time budget (leave 5 min buffer)
        elapsed = time.time() - start_time
        if elapsed > 45 * 60:  # 45 minutes
            log(f'Time budget exhausted after {districts_scraped} districts')
            break

        new_venues = scrape_district_http(dist_id, dist_name, seen_ids)
        all_venues.extend(new_venues)
        completed.append(dist_id)
        districts_scraped += 1

        log(f'  Progress: {len(completed)}/{len(DISTRICTS)} districts, {len(all_venues)} venues')

    progress['completed_districts'] = completed
    progress['total_runs'] = progress.get('total_runs', 0) + 1
    progress['last_run'] = time.strftime('%Y-%m-%d %H:%M:%S')

    save_progress(progress)
    save_venues(all_venues)

    elapsed = time.time() - start_time
    log(f'')
    log(f'=== Session Complete ===')
    log(f'  Districts scraped: {districts_scraped}')
    log(f'  Total venues: {len(all_venues)}')
    log(f'  Districts done: {len(completed)}/{len(DISTRICTS)}')
    log(f'  Time: {elapsed:.1f}s')

if __name__ == '__main__':
    main()
