#!/usr/bin/env python3
"""Capture Foody API responses from main page"""
from playwright.sync_api import sync_playwright
import json

OUTPUT_DIR = 'data/foody-api'

def login(page):
    page.goto('https://id.foody.vn/dang-nhap', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(2000)
    page.fill('#Email', 'simonhart0907@gmail.com')
    page.fill('#Password', '3ypY7rQ9v3n@JJh')
    page.click('input[type="submit"]')
    page.wait_for_timeout(5000)
    return '/tai-khoan' in page.url

def main():
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    captured = []

    def handle_response(response):
        url = response.url
        if '__get' in url or 'directory' in url.lower() or 'IndexAsync' in url:
            try:
                body = response.body()
                text = body.decode('utf-8', errors='ignore')[:2000]
                captured.append({
                    'url': url,
                    'status': response.status,
                    'body_preview': text
                })
            except Exception as e:
                captured.append({
                    'url': url,
                    'status': response.status,
                    'error': str(e)
                })

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()
        page.on('response', handle_response)

        if login(page):
            print("Login OK")

        print("Loading HCM page...")
        page.goto('https://www.foody.vn/ho-chi-minh/', wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(5000)

        print(f"\n=== Captured {len(captured)} API responses ===")
        for r in captured:
            print(f"\n--- {r['status']} ---")
            print(f"URL: {r['url'][:150]}")
            if 'body_preview' in r:
                print(f"Body: {r['body_preview'][:500]}")
            if 'error' in r:
                print(f"Error: {r['error']}")

        with open(f'{OUTPUT_DIR}/captured_api.json', 'w', encoding='utf-8') as f:
            json.dump(captured, f, ensure_ascii=False, indent=2)

        browser.close()

if __name__ == '__main__':
    main()
