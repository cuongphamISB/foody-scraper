#!/usr/bin/env python3
"""
Scrape Foody using route interception to paginate through all venues
"""
import json
import time
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def scrape_foody(max_pages=3500, batch_size=50):
    """
    Scrape all venues from Foody using route interception
    """
    all_venues = []
    seen_ids = set()
    current_page = 1

    print('=' * 60)
    print('Foody Full Scraper')
    print('=' * 60)
    print(f'Target: ~163,658 venues')
    print(f'Batch size: {batch_size}')
    print()

    def on_response(response):
        """Capture IndexAsync response"""
        url = response.url
        if '__get/Directory/IndexAsync' in url:
            try:
                body = response.body().decode('utf-8', errors='ignore')
                if body.strip().startswith('{'):
                    data = json.loads(body)
                    response_queue.append(data)
            except:
                pass

    response_queue = []

    # Create browser and context once
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36'
        )

        while current_page <= max_pages:
            response_queue.clear()

            # Create new page for each request
            page = context.new_page()
            page.on('response', on_response)

            # Route to modify page parameter
            def handle_route(route):
                url = route.request.url
                if '__get/Directory/IndexAsync' in url:
                    # Change page number
                    new_url = re.sub(r'page=\d+', f'page={current_page}', url)
                    # Increase page size
                    new_url = re.sub(r'pageSize=\d+', f'pageSize={batch_size}', new_url)
                    route.continue_(url=new_url)
                else:
                    route.continue_()

            page.route('**/__get/Directory/IndexAsync**', handle_route)

            # Navigate to trigger API call
            try:
                page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                         wait_until='networkidle', timeout=60000)
                page.wait_for_timeout(2000)
            except Exception as e:
                print(f"Page {current_page}: Navigation error - {e}")
                page.close()
                time.sleep(3)
                continue

            page.close()

            if not response_queue:
                print(f"Page {current_page}: No response, retrying...")
                time.sleep(3)
                continue

            data = response_queue[0]
            items = data.get('searchItems', [])
            total = data.get('totalResult', 0)

            if not items:
                print(f"Page {current_page}: Empty response, stopping")
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
                    for c in item.get('Cuisines', []):
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
                        'review_count': item.get('TotalReview'),
                        'cuisines': cuisines,
                        'lat': item.get('Latitude'),
                        'lng': item.get('Longitude'),
                        'phone': item.get('Phone', ''),
                        'url': item.get('Url', ''),
                        'price_range': item.get('PriceRange'),
                        'category': item.get('CategoryGroupKey'),
                        'picture_url': item.get('PicturePath'),
                        'has_booking': item.get('HasBooking'),
                        'has_delivery': item.get('HasDelivery'),
                    }
                    all_venues.append(venue)

            print(f"Page {current_page}/{max_pages}: {len(items)} items ({new_count} new) / ~{total} total | {len(all_venues)} total venues")

            # Progress save
            if current_page % 100 == 0:
                with open(OUTPUT_DIR / 'foody_progress.json', 'w', encoding='utf-8') as f:
                    json.dump({
                        'venues': all_venues,
                        'current_page': current_page,
                        'total': len(all_venues)
                    }, f, ensure_ascii=False)
                print(f"  Progress saved: {len(all_venues)} venues")

            # Rate limit
            time.sleep(0.5)

            current_page += 1

        browser.close()

    return all_venues

def main():
    venues = scrape_foody()

    # Save final
    output_file = OUTPUT_DIR / 'foody_full.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'source': 'foody.vn',
            'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Scraping complete!")
    print(f"Total venues: {len(venues)}")
    print(f"Saved to: {output_file}")

if __name__ == '__main__':
    main()
