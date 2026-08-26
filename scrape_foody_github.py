#!/usr/bin/env python3
"""
Foody Scraper - Multi-city Edition
Scrapes TP.HCM, Hanoi, Da Nang and more cities
"""
import json
import time
import random
import requests
from pathlib import Path

OUTPUT_FILE = Path('data/foody-batch/venues.json')
PROGRESS_FILE = Path('data/foody-batch/progress.json')

# Config - all st values that return data
ST_VALUES = [1, 2, 3, 4, 7, 11, 19, 20]  # 8 sort options
PAGE_SIZE = 50
MAX_PAGES_PER_ST = 5  # 4 pages data + 1 safety buffer
API_DELAY = 0.8

# All cities with their districts - CORRECTED IDs verified from API
CITIES = {
    'TP.HCM': {
        'provinceId': 217,
        'url': 'ho-chi-minh',
        # Verified correct district IDs from API probe
        'districts': [
            (1, 'Quận 1'),
            (2, 'Gò Vấp'),     # ID 2 = Gò Vấp
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
    },
    'Hanoi': {
        'provinceId': 265,
        'url': 'ha-noi',
        'districts': [
            (1, 'Quận Ba Đình'), (2, 'Quận Hoàn Kiếm'), (3, 'Quận Tây Hồ'),
            (4, 'Quận Long Biên'), (5, 'Quận Cầu Giấy'), (6, 'Quận Đống Đa'),
            (7, 'Quận Hai Bà Trưng'), (8, 'Quận Thanh Xuân'), (9, 'Quận Hoàng Mai'),
            (10, 'Quận Bắc Từ Liêm'), (11, 'Quận Nam Từ Liêm'),
            (24, 'Huyện Thanh Trì'), (25, 'Huyện Gia Lâm'), (26, 'Huyện Đông Anh'),
            (27, 'Huyện Sóc Sơn'), (28, 'Huyện Mê Linh'), (29, 'Huyện Hiền Nhai'),
            (30, 'Thị Xã Sơn Tây'), (31, 'Huyện Ba Vì'), (32, 'Huyện Phúc Thọ'),
            (33, 'Huyện Đan Phượng'), (34, 'Huyện Hoài Đức'), (35, 'Huyện Quốc Oai'),
            (36, 'Huyện Thạch Thất'), (37, 'Huyện Chương Mỹ'), (38, 'Huyện Thanh Oai'),
            (39, 'Huyện Mỹ Đức'), (40, 'Huyện Ứng Hòa'), (41, 'Huyện Phú Xuyên'),
        ]
    },
    'DaNang': {
        'provinceId': 273,
        'url': 'da-nang',
        'districts': [
            (1, 'Quận Hải Châu'), (2, 'Quận Thanh Khê'), (3, 'Quận Sơn Trà'),
            (4, 'Quận Ngũ Hành Sơn'), (5, 'Quận Liên Chiểu'),
            (6, 'Quận Cẩm Lệ'), (7, 'Huyện Hòa Vang'), (8, 'Huyện Hoàng Sa'),
        ]
    },
}

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'venues': [], 'completed': {}, 'total_runs': 0, 'last_run': None}

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

def fetch_api(city_url, province_id, district_id, st, page):
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

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def scrape_district(city_name, city_url, province_id, district_id, district_name, seen_ids):
    venues = []
    new_count = 0

    for st in ST_VALUES:
        for page in range(1, MAX_PAGES_PER_ST + 1):
            data = fetch_api(city_url, province_id, district_id, st, page)

            if not data:
                break

            items = data.get('searchItems', [])
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
                        'city': city_name,
                        'rating': item.get('AvgRating'),
                        'reviews': item.get('TotalReview'),
                        'cuisines': cuisines,
                        'lat': item.get('Latitude'),
                        'lng': item.get('Longitude'),
                        'source': 'foody',
                    })
                    new_count += 1

            time.sleep(API_DELAY)

    return venues

def main():
    log('=' * 60)
    log('FOODY SCRAPER - Multi-city Edition')
    log('=' * 60)

    existing = load_existing()
    seen_ids = {v['id'] for v in existing}
    all_venues = existing.copy()

    log(f'Existing venues: {len(all_venues)}')

    progress = load_progress()
    completed = progress.get('completed', {})

    start_time = time.time()

    for city_name, city_info in CITIES.items():
        city_url = city_info['url']
        province_id = city_info['provinceId']
        districts = city_info['districts']

        city_completed = completed.get(city_name, [])

        for district_id, district_name in districts:
            if district_id in city_completed:
                continue

            # Time budget check
            elapsed = time.time() - start_time
            if elapsed > 40 * 60:
                log(f'Time budget exhausted!')
                save_progress(progress)
                save_venues(all_venues)
                return

            log(f'📍 {city_name} - {district_name}')

            new_venues = scrape_district(
                city_name, city_url, province_id, district_id, district_name, seen_ids
            )

            all_venues.extend(new_venues)

            # Mark completed
            if city_name not in completed:
                completed[city_name] = []
            completed[city_name].append(district_id)

            # Save after each district
            progress['completed'] = completed
            progress['total_runs'] = progress.get('total_runs', 0) + 1
            progress['last_run'] = time.strftime('%Y-%m-%d %H:%M:%S')
            save_progress(progress)
            save_venues(all_venues)

            elapsed = time.time() - start_time
            total_districts = sum(len(d['districts']) for d in CITIES.values())
            done_districts = sum(len(v) for v in completed.values())
            log(f'  +{len(new_venues)} venues | {len(all_venues)} total | {done_districts}/{total_districts} districts | {elapsed:.0f}s')

    elapsed = time.time() - start_time
    log(f'')
    log(f'=== COMPLETE! ===')
    log(f'  Total venues: {len(all_venues)}')
    log(f'  Time: {elapsed:.1f}s')

if __name__ == '__main__':
    main()
