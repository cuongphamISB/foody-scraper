#!/usr/bin/env python3
"""
Foody Scraper - Overnight Edition v4
Features:
- Skip pages that consistently fail (track failed pages)
- Auto session restart when blocked
- Progress saved after every page
- Resume from last position
- Backfill failed pages periodically
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
DELAY = 10  # Base delay between pages
MAX_SESSION_PAGES = 30  # Restart session after this many pages
SESSION_COOLDOWN = 180  # 3 min cooldown between sessions
FAIL_COOLDOWN = 300  # 5 min cooldown when failing
MAX_RETRIES = 2  # Max retries per page
SKIP_AFTER_FAILS = 2  # Skip page permanently after this many fails

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    sys.stdout.flush()

def load_progress():
    f = OUTPUT_DIR / 'progress.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('venues', []), data.get('last_page', 0), data.get('failed_pages', {})
    return [], 0, {}

def save_progress(venues, last_page, failed_pages):
    f = OUTPUT_DIR / 'progress.json'
    with open(f, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'last_page': last_page,
            'failed_pages': failed_pages,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False)

def scrape_page(page, page_num):
    responses = []

    def on_response(response):
        if 'IndexAsync' in response.url:
            try:
                body = response.body().decode('utf-8', errors='ignore')
                if body.strip().startswith('{'):
                    responses.append(json.loads(body))
            except:
                pass

    page.on('response', on_response)

    def handle_route(route):
        url = route.request.url
        if 'IndexAsync' in url:
            url = re.sub(r'page=\d+', f'page={page_num}', url)
            url = re.sub(r'pageSize=\d+', f'pageSize={BATCH_SIZE}', url)
            route.continue_(url=url)
        else:
            route.continue_()

    page.route('**/IndexAsync**', handle_route)

    try:
        page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                  wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)
    except:
        pass

    return responses[0] if responses else None

def login(context):
    page = context.new_page()
    page.set_viewport_size({'width': 375, 'height': 812})

    page.goto('https://id.foody.vn/dang-nhap', wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(2000)
    page.fill('#Email', 'simonhart0907@gmail.com')
    page.fill('#Password', '3ypY7rQ9v3n@JJh')
    page.check('#RememberMe')
    page.click('input[type="submit"]')
    page.wait_for_timeout(6000)

    return page if '/tai-khoan' in page.url else None

def run_session(browser, venues, start_page, session_num, failed_pages):
    """Run one scraping session"""
    log(f'=== Session {session_num} from page {start_page + 1} ===')

    context = browser.new_context(
        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
    )

    page = login(context)
    if not page:
        log('Login failed')
        context.close()
        return venues, start_page, failed_pages, False

    log('Login OK')
    seen_ids = {v['id'] for v in venues}
    pages_in_session = 0

    for num in range(start_page + 1, start_page + MAX_SESSION_PAGES + 1):
        # Skip pages that have failed too many times
        if failed_pages.get(num, 0) >= SKIP_AFTER_FAILS:
            log(f'Page {num}: SKIPPED (failed {failed_pages[num]} times)')
            continue

        start = time.time()
        success = False

        for attempt in range(MAX_RETRIES):
            data = scrape_page(page, num)

            if data and data.get('searchItems'):
                items = data['searchItems']
                new_count = 0

                for item in items:
                    vid = f"foody-{item['Id']}"
                    if vid not in seen_ids:
                        seen_ids.add(vid)
                        new_count += 1

                        cuisines = [c['Name'] for c in item.get('Cuisines', [])
                                  if isinstance(c, dict)]

                        venues.append({
                            'id': vid,
                            'name': item.get('Name', ''),
                            'address': item.get('Address', ''),
                            'district': item.get('District', ''),
                            'rating': item.get('AvgRating'),
                            'reviews': item.get('TotalReview'),
                            'cuisines': cuisines,
                            'lat': item.get('Latitude'),
                            'lng': item.get('Longitude'),
                        })

                elapsed = time.time() - start
                log(f'Page {num}: {len(items)} items (+{new_count}) | {len(venues)} total | {elapsed:.1f}s')
                save_progress(venues, num, failed_pages)

                # Reset fail count on success
                if num in failed_pages:
                    del failed_pages[num]

                success = True
                pages_in_session += 1
                break

            elif attempt < MAX_RETRIES - 1:
                wait = DELAY * (attempt + 1) * 2
                log(f'  Retry {attempt + 1} failed, waiting {wait}s...')
                time.sleep(wait)

        if not success:
            log(f'Page {num}: FAILED')
            failed_pages[num] = failed_pages.get(num, 0) + 1
            save_progress(venues, num, failed_pages)

            # Stop session if too many fails
            if len([p for p in failed_pages.values() if p >= SKIP_AFTER_FAILS]) > 5:
                log('Too many failed pages. Ending session.')
                break

        # Delay between pages
        delay = DELAY + random.uniform(-2, 2)
        time.sleep(max(5, delay))

    page.close()
    context.close()

    if pages_in_session > 0:
        log(f'Session {session_num}: {pages_in_session} pages OK')
        return venues, start_page + pages_in_session, failed_pages, True
    else:
        log(f'Session {session_num}: No pages scraped')
        return venues, start_page, failed_pages, False

def main():
    log('=' * 60)
    log('FOODY SCRAPER - OVERNIGHT v4')
    log('=' * 60)

    venues, start_page, failed_pages = load_progress()
    log(f'Loaded: {len(venues)} venues, page {start_page}')
    log(f'Failed pages: {len([p for p in failed_pages.values() if p >= SKIP_AFTER_FAILS])} skipped, {len([p for p in failed_pages.values() if p < SKIP_AFTER_FAILS])} retrying')

    total_target = 163720
    log(f'Target: {total_target:,} venues ({total_target - len(venues):,} remaining)')

    session_num = 1
    consecutive_fails = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        while len(venues) < total_target:
            log(f'\\n--- Iteration {session_num} ---')

            new_venues, new_page, new_failed, ok = run_session(
                browser, venues, start_page, session_num, failed_pages
            )

            venues = new_venues
            start_page = new_page
            failed_pages = new_failed

            if ok:
                consecutive_fails = 0
                if len(venues) >= total_target:
                    break
                log(f'Cooldown {SESSION_COOLDOWN}s...')
                time.sleep(SESSION_COOLDOWN)
            else:
                consecutive_fails += 1
                log(f'Session failed ({consecutive_fails} in a row)')
                log(f'Cooldown {FAIL_COOLDOWN}s...')
                time.sleep(FAIL_COOLDOWN)

            session_num += 1

            if session_num > 1000:
                log('Safety limit reached')
                break

        browser.close()

    # Final save
    output = OUTPUT_DIR / 'foody_full.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': venues,
            'total': len(venues),
            'source': 'foody.vn',
            'completed_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

    log(f'\\n{"="*60}')
    log(f'DONE! {len(venues)} venues ({len(venues)/total_target*100:.1f}%)')
    log(f'Skipped: {len([p for p in failed_pages.values() if p >= SKIP_AFTER_FAILS])} pages')

if __name__ == '__main__':
    main()
