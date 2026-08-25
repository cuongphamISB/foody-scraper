#!/usr/bin/env python3
"""
Foody Scraper using Patchright (undetected Playwright)
Optimized for overnight runs with stealth features
"""
import json
import time
import random
import re
import sys
from pathlib import Path
from patchright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Configuration
BATCH_SIZE = 50
INITIAL_DELAY = 10
MAX_DELAY = 120
JITTER = 5
SAVE_INTERVAL = 50

class Throttle:
    """Enforce minimum gap + jitter between requests"""
    def __init__(self, base_delay=10, jitter=5):
        self.base_delay = base_delay
        self.jitter = jitter
        self.last_request = 0

    def wait(self):
        now = time.time()
        elapsed = now - self.last_request
        delay = self.base_delay + random.uniform(-self.jitter, self.jitter)
        delay = max(1, delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request = time.time()

    def backoff(self):
        self.base_delay = min(self.base_delay * 1.5, MAX_DELAY)

    def reset(self):
        self.base_delay = max(INITIAL_DELAY, self.base_delay * 0.9)

def login(page):
    """Login to Foody"""
    print("Logging in...")
    page.goto('https://id.foody.vn/dang-nhap', wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(2000)

    page.fill('#Email', 'simonhart0907@gmail.com')
    page.fill('#Password', '3ypY7rQ9v3n@JJh')
    page.check('#RememberMe')
    page.click('input[type="submit"]')
    page.wait_for_timeout(6000)

    success = '/tai-khoan' in page.url
    print("Login OK!" if success else "Login may have failed")
    return success

def scrape_page(page, page_num):
    """Scrape a single page using route interception"""
    response_queue = []

    def on_response(response):
        url = response.url
        if '__get/Directory/IndexAsync' in url:
            try:
                body = response.body().decode('utf-8', errors='ignore')
                if body.strip().startswith('{'):
                    response_queue.append(json.loads(body))
            except:
                pass

    page.on('response', on_response)

    def handle_route(route):
        url = route.request.url
        if '__get/Directory/IndexAsync' in url:
            new_url = re.sub(r'page=\d+', f'page={page_num}', url)
            new_url = re.sub(r'pageSize=\d+', f'pageSize={BATCH_SIZE}', new_url)
            route.continue_(url=new_url)
        else:
            route.continue_()

    page.route('**/__get/Directory/IndexAsync**', handle_route)

    try:
        page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                  wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  Navigation error: {e}")

    if response_queue:
        return response_queue[0]
    return None

def load_progress():
    progress_file = OUTPUT_DIR / 'progress.json'
    if progress_file.exists():
        with open(progress_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('venues', []), data.get('last_page', 0)
    return [], 0

def save_progress(venues, last_page):
    progress_file = OUTPUT_DIR / 'progress.json'
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'last_page': last_page,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False)

def main():
    print('=' * 60)
    print('Foody Scraper - Patchright Edition')
    print('=' * 60)
    print(f'Batch size: {BATCH_SIZE}')
    print(f'Delay: {INITIAL_DELAY}s (+/- {JITTER}s jitter)')
    print()

    venues, start_page = load_progress()
    seen_ids = {v['id'] for v in venues}
    print(f'Loaded {len(venues)} venues from page {start_page}')

    throttle = Throttle(INITIAL_DELAY, JITTER)

    print(f'Initial delay {INITIAL_DELAY * 2}s...')
    time.sleep(INITIAL_DELAY * 2)

    with sync_playwright() as p:
        # Launch with stealth settings
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        page = context.new_page()
        login(page)

        consecutive_failures = 0
        total_pages = 3500

        for page_num in range(start_page + 1, total_pages + 1):
            start_time = time.time()

            data = scrape_page(page, page_num)

            if data:
                items = data.get('searchItems', [])

                if items:
                    new_count = 0
                    for item in items:
                        vid = f"foody-{item.get('Id')}"
                        if vid not in seen_ids:
                            seen_ids.add(vid)
                            new_count += 1

                            cuisines = []
                            for c in item.get('Cuisines', []):
                                if isinstance(c, dict):
                                    cuisines.append(c.get('Name', ''))

                            venues.append({
                                'id': vid,
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
                            })

                    elapsed = time.time() - start_time
                    print(f"Page {page_num}: {len(items)} items ({new_count} new) | {len(venues)} total | {elapsed:.1f}s")

                    consecutive_failures = 0
                    throttle.reset()

                    if page_num % SAVE_INTERVAL == 0:
                        save_progress(venues, page_num)
                else:
                    print(f"Page {page_num}: Empty")
                    consecutive_failures += 1
                    throttle.backoff()
            else:
                print(f"Page {page_num}: FAILED")
                consecutive_failures += 1
                throttle.backoff()

            throttle.wait()

            if consecutive_failures >= 10:
                print(f"\nToo many failures. Waiting 5 minutes...")
                time.sleep(300)
                consecutive_failures = 0

        page.close()
        browser.close()

    save_progress(venues, total_pages)

    output_file = OUTPUT_DIR / 'foody_full.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'source': 'foody.vn',
            'completed_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Complete! Total: {len(venues)} venues")
    print(f"Saved to: {output_file}")

if __name__ == '__main__':
    main()
