#!/usr/bin/env python3
"""
Foody Scraper - Final Optimized Version
Uses Playwright with route interception for pagination
Optimized for: long runs, rate limit handling, progress saving
"""
import json
import time
import random
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === CONFIG ===
BATCH_SIZE = 50
INITIAL_DELAY = 15  # seconds between requests
MAX_DELAY = 300     # max backoff seconds
JITTER = 5          # random jitter range
SAVE_EVERY = 25     # save progress every N pages
WARMUP_DELAY = 90   # initial wait before starting
FAIL_THRESHOLD = 15  # restart after N consecutive failures
MAX_RETRIES = 3     # retries per page

class AdaptiveThrottle:
    """
    Smart rate limiter with:
    - Base delay + jitter
    - Exponential backoff on failures
    - Gradual recovery on success
    """
    def __init__(self, base=12, jitter=4, max_delay=180):
        self.base = base
        self.jitter = jitter
        self.max_delay = max_delay
        self.last_request = 0
        self.consecutive_failures = 0

    def wait(self):
        now = time.time()
        elapsed = now - self.last_request

        # Add jitter to base delay
        delay = self.base + random.uniform(-self.jitter, self.jitter)
        delay = max(1, delay)  # minimum 1 second

        if elapsed < delay:
            time.sleep(delay - elapsed)

        self.last_request = time.time()

    def on_success(self):
        """Called on successful request"""
        self.consecutive_failures = 0
        # Gradually reduce delay (conservative)
        self.base = max(INITIAL_DELAY, self.base * 0.95)

    def on_failure(self):
        """Called on failed request"""
        self.consecutive_failures += 1
        # Exponential backoff
        self.base = min(self.base * 1.5, self.max_delay)

    def reset(self):
        self.consecutive_failures = 0
        self.base = INITIAL_DELAY


def load_progress():
    """Load existing progress"""
    f = OUTPUT_DIR / 'progress.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return (data.get('venues', []),
                    data.get('last_page', 0),
                    data.get('delay', INITIAL_DELAY),
                    set(data.get('scraped_pages', [])))
    return [], 0, INITIAL_DELAY, set()


def save_progress(venues, last_page, delay, scraped_pages):
    """Save progress checkpoint"""
    f = OUTPUT_DIR / 'progress.json'
    with open(f, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'last_page': last_page,
            'delay': delay,
            'scraped_pages': sorted(scraped_pages),
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False)


def scrape_one_page(page, page_num):
    """Scrape a single page"""
    responses = []

    def on_response(response):
        url = response.url
        if '__get/Directory/IndexAsync' in url:
            try:
                body = response.body().decode('utf-8', errors='ignore')
                if body.strip().startswith('{'):
                    responses.append(json.loads(body))
            except:
                pass

    page.on('response', on_response)

    def handle_route(route):
        url = route.request.url
        if '__get/Directory/IndexAsync' in url:
            # Modify pagination
            url = re.sub(r'page=\d+', f'page={page_num}', url)
            url = re.sub(r'pageSize=\d+', f'pageSize={BATCH_SIZE}', url)
            route.continue_(url=url)
        else:
            route.continue_()

    page.route('**/__get/Directory/IndexAsync**', handle_route)

    try:
        page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                  wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)
    except:
        pass

    return responses[0] if responses else None


def main():
    print('=' * 60)
    print('FOODY SCRAPER - OVERNIGHT EDITION')
    print('=' * 60)
    print(f'Target: ~163,000 venues')
    print(f'Batch: {BATCH_SIZE}/page | Delay: {INITIAL_DELAY}s ± {JITTER}s')
    print(f'Progress saved every {SAVE_EVERY} pages')
    print()

    # Load progress
    venues, start_page, saved_delay, scraped_pages = load_progress()
    seen_ids = {v['id'] for v in venues}

    print(f'Resumed: {len(venues)} venues from page {start_page}')
    print(f'Already scraped pages: {len(scraped_pages)}')
    print(f'Waiting {WARMUP_DELAY}s for rate limits to clear...')
    time.sleep(WARMUP_DELAY)

    throttle = AdaptiveThrottle(base=saved_delay, jitter=JITTER, max_delay=MAX_DELAY)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36'
        )

        # Login once
        page = context.new_page()
        print('Logging in...')
        page.goto('https://id.foody.vn/dang-nhap', wait_until='domcontentloaded', timeout=45000)
        page.wait_for_timeout(2000)
        page.fill('#Email', 'simonhart0907@gmail.com')
        page.fill('#Password', '3ypY7rQ9v3n@JJh')
        page.check('#RememberMe')
        page.click('input[type="submit"]')
        page.wait_for_timeout(6000)

        if '/tai-khoan' in page.url:
            print('Login successful')
        else:
            print('Login may have failed (continuing anyway)')

        # Main loop
        total_pages = 3500  # ~163k / 50
        consecutive_fail = 0

        for num in range(start_page + 1, total_pages + 1):
            # Skip already scraped pages
            if num in scraped_pages:
                continue

            start = time.time()

            # Retry logic per page
            data = None
            for attempt in range(MAX_RETRIES):
                data = scrape_one_page(page, num)
                if data and data.get('searchItems'):
                    break
                if attempt < MAX_RETRIES - 1:
                    wait_time = throttle.base * (attempt + 1)  # Longer wait for retries
                    print(f'  Retry {attempt + 1} for page {num}, waiting {wait_time}s...')
                    time.sleep(wait_time)

            if data and data.get('searchItems'):
                items = data['searchItems']
                new = 0

                for item in items:
                    vid = f"foody-{item['Id']}"
                    if vid not in seen_ids:
                        seen_ids.add(vid)
                        new += 1

                        cuisines = [
                            c['Name'] for c in item.get('Cuisines', [])
                            if isinstance(c, dict)
                        ]

                        venues.append({
                            'id': vid,
                            'name': item.get('Name', ''),
                            'address': item.get('Address', ''),
                            'district': item.get('District', ''),
                            'city': item.get('City', ''),
                            'rating': item.get('AvgRating'),
                            'reviews': item.get('TotalReview'),
                            'cuisines': cuisines,
                            'lat': item.get('Latitude'),
                            'lng': item.get('Longitude'),
                            'phone': item.get('Phone', ''),
                            'url': item.get('Url', ''),
                        })

                elapsed = time.time() - start
                print(f'Page {num}/{total_pages}: {len(items)} items (+{new}) | {len(venues)} total | {elapsed:.1f}s | delay={throttle.base:.0f}s')

                throttle.on_success()
                consecutive_fail = 0

                # Track scraped pages
                scraped_pages.add(num)

                # Save after every successful page (critical for resume)
                save_progress(venues, num, throttle.base, scraped_pages)

            else:
                print(f'Page {num}: FAILED')
                throttle.on_failure()
                consecutive_fail += 1
                save_progress(venues, num, throttle.base, scraped_pages)

            throttle.wait()

            # Long pause after too many failures
            if consecutive_fail >= FAIL_THRESHOLD:
                print(f'\n⚠ {consecutive_fail} failures. Taking 5min break...')
                time.sleep(300)
                consecutive_fail = 0

        page.close()
        browser.close()

    # Final save
    save_progress(venues, total_pages, throttle.base, scraped_pages)

    output = OUTPUT_DIR / 'foody_full.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'source': 'foody.vn',
            'completed_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*60}')
    print(f'DONE! Total: {len(venues)} venues')
    print(f'Saved: {output}')
    print(f'Progress: {OUTPUT_DIR / "progress.json"}')


if __name__ == '__main__':
    main()
