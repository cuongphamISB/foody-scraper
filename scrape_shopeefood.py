#!/usr/bin/env python3
"""
ShopeeFood Vietnam Scraper
Based on successful GitHub scraper pattern
"""
from playwright.sync_api import sync_playwright
import json
import time
import random
from pathlib import Path

OUTPUT_DIR = Path('data/shopeefood')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# HCM locations
CITIES = ['ho-chi-minh']

def get_restaurant_links(page, max_pages=200):
    """Get all restaurant links from listing pages"""
    links = []

    for page_num in range(1, max_pages + 1):
        print(f'  Page {page_num}...', end=' ')

        try:
            # Wait for restaurant list to load
            page.wait_for_selector('.item-restaurant', timeout=10000)

            # Find all restaurant items
            items = page.query_selector_all('.item-restaurant')
            page_links = []

            for item in items:
                try:
                    link_elem = item.query_selector('a.item-content')
                    if link_elem:
                        href = link_elem.get_attribute('href')
                        if href:
                            page_links.append(href)
                except:
                    pass

            new_count = len([l for l in page_links if l not in links])
            links.extend(page_links)
            print(f'+{new_count} links, Total: {len(links)}')

            if not page_links:
                print('No more restaurants')
                break

            # Click next page
            try:
                next_btn = page.wait_for_selector('span.icon-paging-next', timeout=3000)
                next_btn.click()
                time.sleep(random.uniform(2, 4))
            except:
                print('No next button')
                break

        except Exception as e:
            print(f'Error: {e}')
            break

    return links

def get_restaurant_details(page, url):
    """Get details from a restaurant page"""
    try:
        page.goto(url, timeout=30000)
        page.wait_for_load_state('domcontentloaded')
        time.sleep(random.uniform(1, 2))

        details = {'url': url}

        # Name
        try:
            name = page.query_selector('.name-restaurant')
            if name:
                details['name'] = name.inner_text()
        except:
            pass

        # Address
        try:
            addr = page.query_selector('.address-restaurant')
            if addr:
                details['address'] = addr.inner_text()
        except:
            pass

        # Time
        try:
            time_elem = page.query_selector('.time')
            if time_elem:
                details['time'] = time_elem.inner_text()
        except:
            pass

        # Price
        try:
            price = page.query_selector('.cost-restaurant')
            if price:
                details['price'] = price.inner_text()
        except:
            pass

        return details

    except Exception as e:
        return {'url': url, 'error': str(e)}

def main():
    print('=' * 60)
    print('SHOPEEFOOD VIETNAM SCRAPER')
    print('=' * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for city in CITIES:
            print(f'\n=== Scraping {city} ===')
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='vi-VN',
            )
            page = context.new_page()

            # Get restaurant links
            url = f'https://shopeefood.vn/{city}/food/deals'
            print(f'Loading: {url}')
            page.goto(url, timeout=60000)
            page.wait_for_load_state('networkidle')
            time.sleep(3)

            print('\nExtracting restaurant links...')
            links = get_restaurant_links(page, max_pages=200)
            print(f'\nTotal links: {len(links)}')

            # Save links
            with open(OUTPUT_DIR / f'{city}_links.txt', 'w') as f:
                for link in links:
                    f.write(link + '\n')

            page.close()
            context.close()

        browser.close()

    print('\n' + '=' * 60)
    print(f'DONE! Links saved to {OUTPUT_DIR}')
    print('=' * 60)

if __name__ == '__main__':
    main()
