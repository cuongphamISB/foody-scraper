#!/usr/bin/env python3
"""
Scrape Foody IndexAsync API by intercepting responses
"""
import json
import time
import sys
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path('data/foody-full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Thread-safe storage
all_items = []
all_items_lock = threading.Lock()
seen_ids = set()
seen_lock = threading.Lock()

def scrape_page(page, page_num):
    """Scrape a single page"""
    api_url = f"https://www.foody.vn/__get/Directory/IndexAsync?ds=Restaurant&page={page_num}&pageSize=50&q=&Lat=0&Lon=0&vt=row&st=7&append=true"

    page.goto(api_url, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(1000)

    # Extract data from Angular scope
    result = page.evaluate('''
    (function() {
        var elements = document.querySelectorAll('[ng-controller]');
        for (var el of elements) {
            var scope = angular.element(el).scope();
            if (scope && scope.SearchItems) {
                return JSON.stringify(scope.SearchItems);
            }
        }
        return null;
    })()
    ''')

    if result:
        items = json.loads(result)
        return items
    return []

def main():
    global all_items, seen_ids

    print('=' * 60)
    print('Foody IndexAsync Scraper')
    print('=' * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Load main page first
        print("Loading main page...")
        page.goto('https://www.foody.vn/ho-chi-minh/', wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)

        # Get total from first page
        print("Getting total...")
        items = scrape_page(page, 1)

        if items:
            # Get total from scope
            total = page.evaluate('''
            (function() {
                var elements = document.querySelectorAll('[ng-controller]');
                for (var el of elements) {
                    var scope = angular.element(el).scope();
                    if (scope) {
                        return scope.TotalResult || scope.totalResult;
                    }
                }
                return null;
            })()
            ''')

            print(f"Total venues: {total}")
            print(f"Items per page: {len(items)}")

            # Store first page items
            for item in items:
                vid = item.get('Id')
                if vid and vid not in seen_ids:
                    seen_lock.acquire()
                    if vid not in seen_ids:
                        seen_ids.add(vid)
                        all_items.append(item)
                    seen_lock.release()

            print(f"Page 1: {len(items)} venues")

            # Scrape remaining pages
            total_pages = 3000  # 163k / 50 = ~3300 pages

            for page_num in range(2, total_pages + 1):
                items = scrape_page(page, page_num)

                if not items:
                    print(f"Page {page_num}: Empty, stopping")
                    break

                # Store items
                new_count = 0
                for item in items:
                    vid = item.get('Id')
                    if vid and vid not in seen_ids:
                        seen_lock.acquire()
                        if vid not in seen_ids:
                            seen_ids.add(vid)
                            all_items.append(item)
                            new_count += 1
                        seen_lock.release()

                print(f"Page {page_num}: {len(items)} venues ({new_count} new)")

                # Rate limit protection
                if page_num % 10 == 0:
                    time.sleep(1)

                # Progress save
                if page_num % 50 == 0:
                    with open(OUTPUT_DIR / 'progress.json', 'w', encoding='utf-8') as f:
                        json.dump({
                            'venues': all_items,
                            'count': len(all_items)
                        }, f, ensure_ascii=False)
                    print(f"Progress saved: {len(all_items)} venues")
        else:
            print("Failed to get first page")

        browser.close()

    # Save final
    with open(OUTPUT_DIR / 'foody_indexasync.json', 'w', encoding='utf-8') as f:
        json.dump({
            'venues': all_items,
            'total': len(all_items)
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Total venues: {len(all_items)}")
    print(f"Saved to: {OUTPUT_DIR / 'foody_indexasync.json'}")

if __name__ == '__main__':
    main()
