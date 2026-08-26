#!/usr/bin/env python3
"""
Foody Scraper v3 - Fixed for FULL HCM coverage

Fixes:
1. Real ceiling detection (stop on empty, not totalEstimate)
2. Retry failed pages
3. Only update timestamp when new venues added
4. Checkpoint after each district
5. Coverage gate with minimum threshold
"""
import json
import time
import random
import requests
from pathlib import Path
from datetime import datetime

OUTPUT_FILE = Path('data/foody-batch/venues.json')
PROGRESS_FILE = Path('data/foody-batch/progress.json')
MANIFEST_FILE = Path('data/foody-batch/manifest.json')

# Config - verified ceiling is 4 pages per st
ST_VALUES = [1, 2, 3, 4, 7, 11, 19, 20]  # 8 sort options
PAGE_SIZE = 50
MAX_PAGES_PER_ST = 5  # 4 pages data + 1 safety buffer
API_DELAY = 0.5
MAX_RETRIES = 2
MIN_VENUES_PER_DISTRICT = 10  # Coverage gate

# TP.HCM districts - verified correct IDs from API
CITY_CONFIG = {
    'TP.HCM': {
        'provinceId': 217,
        'url': 'ho-chi-minh',
        'districts': [
            (1, 'Quận 1'),
            (2, 'Gò Vấp'),        # ID 2 = Gò Vấp
            (4, 'Quận 2'),
            (5, 'Quận 3'),
            (6, 'Quận 4'),
            (8, 'Quận 6'),
            (9, 'Quận 7'),
            (10, 'Quận 8'),
            (11, 'Quận 9'),
            (12, 'Quận 10'),
            (13, 'Quận 11'),
            (14, 'Quận 12'),
            (15, 'Bình Thạnh'),
            (16, 'Tân Bình'),
            (17, 'Phú Nhuận'),
            (18, 'Bình Tân'),
            (19, 'Tân Phú'),
        ]
    }
}

# Districts not in API (suburbs/huyện):
# 3, 7, 20, 21, 22, 24, 25, 26, 27, 28

def log(msg, level='INFO'):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] [{level}] {msg}', flush=True)

def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'venues': [],
        'completed': {},
        'total_runs': 0,
        'last_run': None,
        'last_data_run': None  # Only update when data actually changes
    }

def save_progress(data):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_existing():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('venues', [])
    return []

def save_venues(venues, updated=False):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Read current to preserve updated_at
    current_ts = None
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            try:
                current = json.load(f)
                current_ts = current.get('updated_at')
            except:
                pass

    # Only update timestamp if new data was added
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if updated else current_ts

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'updated_at': ts or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

def save_manifest(coverage_stats):
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(coverage_stats, f, ensure_ascii=False, indent=2)

def fetch_api(city_url, province_id, district_id, st, page, retries=MAX_RETRIES):
    url = (
        f'https://www.foody.vn/{city_url}/food/dia-diem'
        f'?ds=Restaurant&vt=row&st={st}&provinceId={province_id}'
        f'&dt={district_id}&page={page}&pageSize={PAGE_SIZE}'
        f'&t={int(time.time() * 1000)}'
    )

    headers = {
        'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/{random.randint(120,127)}.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json',
        'Accept-Language': 'vi-VN,vi;q=0.9',
    }

    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                log(f'Rate limited, waiting...', 'RATE')
                time.sleep(5)
        except Exception as e:
            log(f'Attempt {attempt+1} error: {e}', 'WARN')

        if attempt < retries - 1:
            time.sleep(2)

    return None

def scrape_district(city_name, city_url, province_id, district_id, district_name, seen_ids):
    """Scrape one district with proper pagination detection"""
    venues = []
    page_stats = []
    consecutive_empty = 0

    for st in ST_VALUES:
        for page in range(1, MAX_PAGES_PER_ST + 1):
            data = fetch_api(city_url, province_id, district_id, st, page)

            if data is None:
                log(f'  st={st} p={page}: API error', 'WARN')
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    log(f'  Multiple failures, stopping st loop', 'WARN')
                    break
                continue

            items = data.get('searchItems', [])
            count = len(items)
            page_stats.append({'st': st, 'page': page, 'count': count})

            if count == 0:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    # Real ceiling reached for this st
                    log(f'  st={st}: ceiling reached at page {page}', 'DEBUG')
                    break
            else:
                consecutive_empty = 0  # Reset on successful page

            # Extract venues
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
                        'city': city_name,
                        'rating': item.get('AvgRating'),
                        'reviews': item.get('TotalReview'),
                        'cuisines': cuisines,
                        'lat': item.get('Latitude'),
                        'lng': item.get('Longitude'),
                        'source': 'foody',
                    })

            time.sleep(API_DELAY)

    return venues, page_stats

def main():
    log('=' * 60)
    log('FOODY SCRAPER v3 - FULL HCM')
    log('=' * 60)

    # Load existing data
    existing = load_existing()
    seen_ids = {v['id'] for v in existing}
    all_venues = existing.copy()

    log(f'Existing venues: {len(all_venues)}')
    log(f'Target: 17 districts x 8 st x 4 pages x 50 items')

    progress = load_progress()
    completed = progress.get('completed', {})

    start_time = time.time()
    total_districts = sum(len(c['districts']) for c in CITY_CONFIG.values())
    done_districts = 0

    coverage_stats = {
        'districts': {},
        'total_venues': len(all_venues),
        'start_time': datetime.now().isoformat()
    }

    for city_name, city_info in CITY_CONFIG.items():
        city_url = city_info['url']
        province_id = city_info['provinceId']

        for district_id, district_name in city_info['districts']:
            # Skip if completed
            if completed.get(city_name, []):
                if district_id in completed[city_name]:
                    continue

            # Time budget check (40 min)
            elapsed = time.time() - start_time
            if elapsed > 40 * 60:
                log('Time budget exhausted!')
                save_progress(progress)
                save_venues(all_venues, updated=False)
                save_manifest(coverage_stats)
                return

            log(f'Scraping: {city_name} - {district_name}')

            district_venues, page_stats = scrape_district(
                city_name, city_url, province_id, district_id, district_name, seen_ids
            )

            # Coverage gate
            if len(district_venues) < MIN_VENUES_PER_DISTRICT:
                log(f'  WARNING: Only {len(district_venues)} venues (expected >={MIN_VENUES_PER_DISTRICT})', 'WARN')
                log(f'  Page stats: {page_stats}', 'WARN')

            all_venues.extend(district_venues)
            new_count = len(district_venues)

            # Mark completed
            if city_name not in completed:
                completed[city_name] = []
            completed[city_name].append(district_id)
            done_districts += 1

            # Update progress
            progress['completed'] = completed
            progress['total_runs'] = progress.get('total_runs', 0) + 1
            progress['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Only update last_data_run if we got new venues
            if new_count > 0:
                progress['last_data_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            save_progress(progress)
            save_venues(all_venues, updated=new_count > 0)

            # Update coverage stats
            coverage_stats['districts'][district_id] = {
                'name': district_name,
                'venues': len(district_venues),
                'pages': len([p for p in page_stats if p['count'] > 0])
            }
            coverage_stats['total_venues'] = len(all_venues)
            save_manifest(coverage_stats)

            elapsed = time.strftime('%M:%S', time.gmtime(time.time() - start_time))
            log(f'  +{new_count} new | {len(all_venues)} total | {done_districts}/{total_districts} districts | {elapsed}')

    elapsed = time.time() - start_time
    log('')
    log('=' * 60)
    log('COMPLETE!')
    log(f'  Total venues: {len(all_venues)}')
    log(f'  Districts: {done_districts}/{total_districts}')
    log(f'  Time: {elapsed}')

    coverage_stats['end_time'] = datetime.now().isoformat()
    coverage_stats['elapsed_seconds'] = elapsed
    save_manifest(coverage_stats)

if __name__ == '__main__':
    main()
