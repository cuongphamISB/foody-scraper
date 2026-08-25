#!/usr/bin/env python3
"""
GrabFood Vietnam Scraper - Direct API approach
Uses exported cookies and direct API calls for better speed
"""
import json
import time
import random
import requests
from pathlib import Path

# === CONFIG ===
COOKIE_FILE = 'C:/Users/Admin/Downloads/food.grab.com_24-08-2026.json'
OUTPUT_DIR = Path('data/grabfood')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# HCM locations (different districts)
LOCATIONS = [
    (10.7769, 106.7009, 'District 1'),
    (10.7869, 106.6809, 'District 3'),
    (10.7569, 106.7209, 'District 5'),
    (10.8069, 106.6409, 'Binh Thanh'),
    (10.7369, 106.7409, 'District 8'),
    (10.7969, 106.6609, 'Phu Nhuan'),
    (10.8169, 106.6209, 'Tan Binh'),
    (10.7469, 106.7609, 'District 7'),
    (10.8369, 106.6009, 'Go Vap'),
    (10.8569, 106.5809, 'Hoc Mon'),
    (10.7269, 106.7209, 'District 6'),
    (10.7669, 106.6809, 'District 10'),
    (10.8169, 106.7009, 'Thu Duc'),
    (10.8769, 106.5609, 'District 12'),
    (10.8469, 106.6409, 'Nam Sa'),
    (10.7569, 106.6509, 'District 11'),
    (10.8369, 106.6609, 'Tan Phu'),
    (10.8169, 106.5809, 'Tan Binh'),
    (10.7769, 106.6309, 'District 3'),
    (10.8469, 106.6109, 'Binh Tan'),
]

def load_cookies():
    """Load cookies from exported JSON file"""
    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookies_data = json.load(f)

    # Convert to requests format
    cookies = {}
    for c in cookies_data:
        cookies[c['name']] = c['value']
    return cookies

def load_progress():
    """Load scraping progress"""
    f = OUTPUT_DIR / 'progress.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('venues', []), data.get('last_location', 0)
    return [], 0

def save_progress(venues, last_location):
    """Save scraping progress"""
    f = OUTPUT_DIR / 'progress.json'
    with open(f, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'last_location': last_location,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False)

def scrape_location(cookies, lat, lng, district_name):
    """Scrape all venues from a location using direct API"""
    all_merchants = []
    seen_ids = set()

    url = 'https://portal.grab.com/foodweb/guest/v2/category'

    for offset in range(0, 200, 20):
        params = {
            'latlng': f'{lat},{lng}',
            'categoryShortcutID': '305',
            'offset': str(offset),
            'pageSize': '20',
            'countryCode': 'VN',
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        try:
            resp = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=30)

            if resp.status_code != 200:
                print(f"    Offset {offset}: HTTP {resp.status_code}")
                break

            data = resp.json()
            search_result = data.get('searchResult', {})
            merchants = search_result.get('searchMerchants', [])
            has_more = search_result.get('hasMore', False)

            new_count = 0
            for m in merchants:
                mid = f"grab-{m.get('id', '')}"
                if mid not in seen_ids:
                    seen_ids.add(mid)
                    brief = m.get('merchantBrief', {})
                    addr = m.get('address', {})

                    merchant = {
                        'id': mid,
                        'name': brief.get('name', ''),
                        'address': addr.get('name', ''),
                        'district': district_name,
                        'cuisines': brief.get('cuisine', []),
                        'rating': brief.get('rating', 0),
                        'rating_count': brief.get('ratingCount', 0),
                        'price_level': brief.get('priceLevel', 0),
                        'photo_url': brief.get('photoHref', ''),
                        'lat': addr.get('lat', lat),
                        'lng': addr.get('lng', lng),
                        'delivery_time': m.get('estimatedDeliveryTime', ''),
                        'delivery_fee': m.get('estimatedDeliveryFee', {}).get('priceDisplay', ''),
                        'source': 'grabfood'
                    }
                    all_merchants.append(merchant)
                    new_count += 1

            print(f"    Offset {offset}: HTTP {resp.status_code}, Total: {len(merchants)}, New: {new_count}, HasMore: {has_more}")

            if not has_more or not merchants:
                break

            # Small delay between requests
            time.sleep(random.uniform(0.5, 1.5))

        except Exception as e:
            print(f"    Offset {offset}: Error - {e}")
            break

    return all_merchants

def main():
    print('=' * 60)
    print('GRABFOOD VIETNAM SCRAPER - Direct API')
    print('=' * 60)

    # Load cookies
    cookies = load_cookies()
    print(f'Loaded {len(cookies)} cookies from export')

    # Load progress
    venues, start_loc = load_progress()
    seen_ids = {v['id'] for v in venues}

    print(f'Loaded: {len(venues)} venues from location {start_loc}')
    print(f'Target locations: {len(LOCATIONS)}')
    print()

    new_total = 0

    for i in range(start_loc, len(LOCATIONS)):
        lat, lng, name = LOCATIONS[i]
        print(f'[{i+1}/{len(LOCATIONS)}] Scraping {name} ({lat}, {lng})...')

        merchants = scrape_location(cookies, lat, lng, name)
        new_count = 0

        for m in merchants:
            if m['id'] not in seen_ids:
                seen_ids.add(m['id'])
                venues.append(m)
                new_count += 1
                new_total += 1

        print(f'  -> {len(merchants)} merchants (+{new_count} new), Total: {len(venues)} venues')

        # Save progress
        save_progress(venues, i + 1)

        # Random delay between locations
        time.sleep(random.uniform(1, 3))

    # Save final
    output = OUTPUT_DIR / 'grabfood_full.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'source': 'grabfood.com',
            'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

    print()
    print('=' * 60)
    print(f'DONE! {len(venues)} total venues (+{new_total} new)')
    print(f'Saved: {output}')
    print('=' * 60)

if __name__ == '__main__':
    main()
