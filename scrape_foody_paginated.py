#!/usr/bin/env python3
"""
Scrape Foody using page.route() to paginate through all venues
"""
import json
import time
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def scrape_foody():
    """Main scraping function"""
    all_venues = []
    seen_ids = set()
    current_page = 1
    max_pages = 4000  # 37262 / 10 = ~3700 pages
    batch_size = 10

    print('=' * 60)
    print('Foody Paginated Scraper')
    print('=' * 60)

    captured = []

    def modify_route(route):
        """Modify request to paginate"""
        url = route.request.url
        if 'Mobile_HomeListPlace' in url:
            # Change Page and Count
            new_url = url.replace(f'Page={current_page - 1}', f'Page={current_page}')
            new_url = new_url.replace('Count=10', f'Count={batch_size}')
            route.continue_(url=new_url)
        else:
            route.continue_()

    def on_response(response):
        """Capture API responses"""
        url = response.url
        if 'Mobile_HomeListPlace' in url:
            try:
                body = response.body().decode('utf-8', errors='ignore')
                if body.strip().startswith('{'):
                    data = json.loads(body)
                    captured.append(data)
            except:
                pass

    while current_page <= max_pages:
        captured.clear()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()

            # Route to modify requests
            page.route('**/Mobile_HomeListPlace**', modify_route)
            page.on('response', on_response)

            # Navigate to trigger API call
            page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                     wait_until='networkidle', timeout=60000)
            page.wait_for_timeout(2000)

            browser.close()

        if not captured:
            print(f"Page {current_page}: No response, retrying...")
            time.sleep(3)
            continue

        data = captured[0]
        items = data.get('Items', [])
        total = data.get('Total', 0)

        if not items:
            print(f"Page {current_page}: Empty, stopping")
            break

        # Extract venues
        new_count = 0
        for item in items:
            vid = item.get('Id')
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                new_count += 1

                # Extract cuisines
                cuisines = []
                if item.get('LstCuisine'):
                    for c in item['LstCuisine']:
                        if isinstance(c, dict):
                            cuisines.append(c.get('Name', ''))
                        elif isinstance(c, str):
                            cuisines.append(c)

                venue = {
                    'id': f"foody-{vid}",
                    'name': item.get('Name', ''),
                    'address': item.get('Address', ''),
                    'district': item.get('District', ''),
                    'city': item.get('City', ''),
                    'rating': item.get('AvgRating'),
                    'review_count': item.get('TotalReviews'),
                    'cuisines': cuisines,
                    'lat': item.get('Latitude'),
                    'lng': item.get('Longitude'),
                    'phone': item.get('Phone', ''),
                    'url': item.get('Url', ''),
                    'price_min': item.get('PriceMin'),
                    'price_max': item.get('PriceMax'),
                    'has_booking': item.get('IsBooking'),
                    'has_delivery': item.get('IsDelivery'),
                    'photo_url': item.get('PhotoUrl'),
                }
                all_venues.append(venue)

        print(f"Page {current_page}: {len(items)} items ({new_count} new) / {total} total")

        # Progress save
        if current_page % 50 == 0:
            with open(OUTPUT_DIR / 'foody_progress.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'venues': all_venues,
                    'current_page': current_page,
                    'total': len(all_venues)
                }, f, ensure_ascii=False)
            print(f"Progress saved: {len(all_venues)} venues")

        # Rate limit
        time.sleep(1)

        current_page += 1

    return all_venues

def main():
    venues = scrape_foody()

    # Save final
    with open(OUTPUT_DIR / 'foody_full.json', 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'source': 'foody.vn'
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Total venues: {len(venues)}")
    print(f"Saved to: {OUTPUT_DIR / 'foody_full.json'}")

if __name__ == '__main__':
    main()
