#!/usr/bin/env python3
"""
GrabFood Vietnam Scraper
Uses Playwright to capture API responses from GrabFood
"""
import json
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

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
]

def load_progress():
    f = OUTPUT_DIR / 'progress.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('venues', []), data.get('last_location', 0)
    return [], 0

def save_progress(venues, last_location):
    f = OUTPUT_DIR / 'progress.json'
    with open(f, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'last_location': last_location,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False)

def scrape_location(browser, lat, lng, district_name):
    """Scrape restaurants from a specific location"""
    merchants = []

    context = browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        geolocation={'latitude': lat, 'longitude': lng}
    )
    page = context.new_page()

    # Inject location cookies
    context.add_cookies([
        {'name': 'gfc-country', 'value': 'VN', 'domain': '.grab.com', 'path': '/'},
        {'name': 'gfc-latlng', 'value': f'{lat},{lng}', 'domain': '.grab.com', 'path': '/'}
    ])

    def on_response(response):
        url = response.url
        if 'portal.grab.com' in url and 'category' in url:
            try:
                data = response.json()
                if 'searchResult' in data and 'searchMerchants' in data['searchResult']:
                    for m in data['searchResult']['searchMerchants']:
                        brief = m.get('merchantBrief', {})
                        addr = m.get('address', {})

                        merchant = {
                            'id': f"grab-{m.get('id', '')}",
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
                        merchants.append(merchant)
            except:
                pass

    page.on('response', on_response)

    try:
        page.goto('https://food.grab.com/vn/en/', wait_until='networkidle', timeout=60000)
        time.sleep(3)
    except:
        pass

    page.close()
    context.close()

    return merchants

def main():
    print('=' * 60)
    print('GRABFOOD VIETNAM SCRAPER')
    print('=' * 60)

    venues, start_loc = load_progress()
    seen_ids = {v['id'] for v in venues}

    print(f'Loaded: {len(venues)} venues from location {start_loc}')
    print(f'Target locations: {len(LOCATIONS)}')

    new_total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for i in range(start_loc, len(LOCATIONS)):
            lat, lng, name = LOCATIONS[i]
            print(f'\n[{i+1}/{len(LOCATIONS)}] Scraping {name} ({lat}, {lng})...')

            merchants = scrape_location(browser, lat, lng, name)
            new_count = 0

            for m in merchants:
                if m['id'] not in seen_ids:
                    seen_ids.add(m['id'])
                    venues.append(m)
                    new_count += 1
                    new_total += 1

            print(f'  Found {len(merchants)} merchants (+{new_count} new)')
            print(f'  Total: {len(venues)} venues')

            # Save progress
            save_progress(venues, i + 1)

            # Random delay between locations
            time.sleep(random.uniform(2, 5))

        browser.close()

    # Save final
    output = OUTPUT_DIR / 'grabfood_full.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'source': 'grabfood.com'
        }, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*60}')
    print(f'DONE! {len(venues)} total (+{new_total} new)')
    print(f'Saved: {output}')

if __name__ == '__main__':
    main()
