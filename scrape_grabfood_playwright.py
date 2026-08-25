#!/usr/bin/env python3
"""
GrabFood Vietnam Scraper - Playwright interception approach
Intercepts API responses directly from the browser
"""
from playwright.sync_api import sync_playwright
import json
import time
import random
from pathlib import Path

OUTPUT_DIR = Path('data/grabfood')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# HCM locations
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

def scrape_location_with_intercept(browser, lat, lng, district_name):
    """Scrape by intercepting API responses"""
    merchants = []

    # Create new context with location
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        geolocation={'latitude': lat, 'longitude': lng},
        permissions=['geolocation'],
    )

    # Inject location cookies
    context.add_cookies([
        {'name': 'gfc-country', 'value': 'VN', 'domain': '.grab.com', 'path': '/'},
        {'name': 'gfc-latlng', 'value': f'{lat},{lng}', 'domain': '.grab.com', 'path': '/'}
    ])

    page = context.new_page()

    # Set up interception
    captured_data = []

    def handle_response(response):
        url = response.url
        # Capture category and search API responses
        if ('category' in url or 'search' in url) and 'portal.grab.com' in url:
            try:
                data = response.json()
                captured_data.append(data)
            except:
                pass

    page.on('response', handle_response)

    try:
        # Navigate to trigger API calls
        page.goto('https://food.grab.com/vn/en/', wait_until='networkidle', timeout=60000)
        time.sleep(3)

        # Scroll to trigger more API calls
        for _ in range(5):
            page.evaluate('window.scrollBy(0, 500)')
            time.sleep(0.5)

        time.sleep(2)

    except Exception as e:
        print(f'Navigation error: {e}')

    # Extract merchants from captured data
    seen_ids = set()
    for data in captured_data:
        # Try different response structures
        search_result = data.get('searchResult', {})
        if isinstance(search_result, dict):
            merchant_list = search_result.get('searchMerchants', [])
        else:
            merchant_list = []

        for m in merchant_list:
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
                merchants.append(merchant)

    page.close()
    context.close()

    return merchants

def main():
    print('=' * 60)
    print('GRABFOOD SCRAPER - Playwright Interception')
    print('=' * 60)

    venues, start_loc = load_progress()
    seen_ids = {v['id'] for v in venues}

    print(f'Loaded: {len(venues)} venues from location {start_loc}')
    print(f'Target locations: {len(LOCATIONS)}')
    print()

    new_total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for i in range(start_loc, len(LOCATIONS)):
            lat, lng, name = LOCATIONS[i]
            print(f'[{i+1}/{len(LOCATIONS)}] Scraping {name} ({lat}, {lng})...')

            merchants = scrape_location_with_intercept(browser, lat, lng, name)
            new_count = 0

            for m in merchants:
                if m['id'] not in seen_ids:
                    seen_ids.add(m['id'])
                    venues.append(m)
                    new_count += 1
                    new_total += 1

            print(f'  -> {len(merchants)} merchants (+{new_count} new), Total: {len(venues)}')

            save_progress(venues, i + 1)
            time.sleep(random.uniform(2, 4))

        browser.close()

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
    print(f'DONE! {len(venues)} total (+{new_total} new)')
    print(f'Saved: {output}')
    print('=' * 60)

if __name__ == '__main__':
    main()
