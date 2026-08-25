#!/usr/bin/env python3
"""
Simple backfill scraper - outputs to file
"""
import json
import time
import random
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
LOG_FILE = OUTPUT_DIR / 'backfill.log'
BATCH_SIZE = 50
DELAY = 30  # Increased delay
MAX_RETRIES = 5

def log(msg):
    """Log to file"""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    print(msg)

def load_progress():
    """Load progress to get missing pages"""
    f = OUTPUT_DIR / 'progress.json'
    if f.exists():
        with open(f, 'r', encoding='utf-8') as f:
            data = json.load(f)
            scraped = set(data.get('scraped_pages', []))
            last_page = data.get('last_page', 0)
            start_page = 19
            attempted = set(range(start_page, last_page + 1))
            missing = sorted(attempted - scraped)
            return missing, data.get('venues', []), scraped
    return [], [], set()

def scrape_page(page, page_num):
    responses = []

    def on_resp(r):
        if '__get/Directory/IndexAsync' in r.url:
            try:
                b = r.body().decode('utf-8', errors='ignore')
                if b.strip().startswith('{'):
                    responses.append(json.loads(b))
            except: pass

    page.on('response', on_resp)

    def handle(route):
        url = route.request.url
        if '__get/Directory/IndexAsync' in url:
            url = re.sub(r'page=\d+', f'page={page_num}', url)
            url = re.sub(r'pageSize=\d+', f'pageSize={BATCH_SIZE}', url)
            route.continue_(url=url)
        else:
            route.continue_()

    page.route('**/__get/Directory/IndexAsync**', handle)

    try:
        page.goto('https://www.foody.vn/ho-chi-minh/o-dau', wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)
    except: pass

    return responses[0] if responses else None

def main():
    log("="*50)
    log("BACKFILL SCRAPER STARTED")
    log("="*50)

    missing_pages, existing_venues, existing_ids = load_progress()
    seen_ids = {v['id'] for v in existing_venues}

    log(f"Existing venues: {len(existing_venues)}")
    log(f"Missing pages: {len(missing_pages)}")
    log(f"Pages: {missing_pages}")

    if not missing_pages:
        log("No missing pages to scrape")
        return

    backfill_venues = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36'
        )

        # Login
        login_page = context.new_page()
        log("Logging in...")
        login_page.goto('https://id.foody.vn/dang-nhap', wait_until='domcontentloaded', timeout=45000)
        login_page.wait_for_timeout(2000)
        login_page.fill('#Email', 'simonhart0907@gmail.com')
        login_page.fill('#Password', '3ypY7rQ9v3n@JJh')
        login_page.check('#RememberMe')
        login_page.click('input[type="submit"]')
        login_page.wait_for_timeout(6000)
        login_page.close()

        log("Login done. Waiting 60s...")
        time.sleep(60)

        # Create new page for scraping
        page = context.new_page()

        success = 0
        failed = 0

        for page_num in missing_pages:
            data = None
            for attempt in range(MAX_RETRIES):
                data = scrape_page(page, page_num)
                if data and data.get('searchItems'):
                    break
                if attempt < MAX_RETRIES - 1:
                    log(f"  Retry {attempt+1} page {page_num}...")
                    time.sleep(DELAY * (attempt + 1))

            if data and data.get('searchItems'):
                items = data['searchItems']
                new = 0
                for item in items:
                    vid = f"foody-{item['Id']}"
                    if vid not in seen_ids:
                        seen_ids.add(vid)
                        new += 1
                        cuisines = [c['Name'] for c in item.get('Cuisines', []) if isinstance(c, dict)]
                        backfill_venues.append({
                            'id': vid,
                            'name': item.get('Name', ''),
                            'address': item.get('Address', ''),
                            'district': item.get('District', ''),
                            'rating': item.get('AvgRating'),
                            'reviews': item.get('TotalReview'),
                            'cuisines': cuisines,
                        })
                log(f"Page {page_num}: +{new} venues, total backfill: {len(backfill_venues)}")
                success += 1

                # Update scraped_pages in progress
                progress_file = OUTPUT_DIR / 'progress.json'
                with open(progress_file, 'r', encoding='utf-8') as pf:
                    prog = json.load(pf)
                if page_num not in prog.get('scraped_pages', []):
                    prog['scraped_pages'] = prog.get('scraped_pages', []) + [page_num]
                    with open(progress_file, 'w', encoding='utf-8') as pf:
                        json.dump(prog, pf, ensure_ascii=False)

                # Periodic save
                if len(backfill_venues) % 100 == 0:
                    with open(OUTPUT_DIR / 'foody_backfill.json', 'w', encoding='utf-8') as f:
                        json.dump({'venues': backfill_venues}, f, ensure_ascii=False, indent=2)
                    log(f"  Saved: {len(backfill_venues)} backfill venues")

            else:
                log(f"Page {page_num}: FAILED")
                failed += 1

            time.sleep(DELAY + random.uniform(-5, 5))

        page.close()
        browser.close()

    # Save
    log(f"\nBackfill complete: {success} success, {failed} failed")
    log(f"New venues: {len(backfill_venues)}")

    with open(OUTPUT_DIR / 'foody_backfill.json', 'w', encoding='utf-8') as f:
        json.dump({'venues': backfill_venues, 'pages': len(missing_pages)}, f, ensure_ascii=False, indent=2)

    log(f"Saved to foody_backfill.json")

if __name__ == '__main__':
    main()
