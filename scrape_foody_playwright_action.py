#!/usr/bin/env python3
"""
Foody Scraper - Debug data structure
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_FILE = Path('data/foody-batch/venues.json')

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def main():
    log('FOODY DEBUG - Checking data structure')

    captured = []

    with sync_playwright() as p:
        context = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        ).new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
        )

        page = context.new_page()

        def capture_response(response):
            url = response.url
            if 'Directory' in url or 'HomeList' in url or 'IndexAsync' in url:
                try:
                    body = response.body()
                    if body:
                        text = body.decode('utf-8', errors='ignore')
                        if text.strip().startswith('{'):
                            data = json.loads(text)
                            captured.append({
                                'url': url,
                                'keys': list(data.keys()) if isinstance(data, dict) else 'list',
                                'sample': data if not isinstance(data, dict) else {k: str(v)[:50] if len(str(v)) > 50 else v for k, v in list(data.items())[:5]}
                            })
                except:
                    pass

        page.on('response', capture_response)

        log('Navigating...')
        page.goto('https://www.foody.vn/ho-chi-minh/o-dau',
                 wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(3000)

        log(f'Captured {len(captured)} responses')

        for i, c in enumerate(captured):
            log(f'\n--- Response {i+1} ---')
            log(f'URL: {c["url"][:100]}')
            log(f'Keys: {c["keys"]}')
            if c['sample']:
                log(f'Sample: {json.dumps(c["sample"], ensure_ascii=False)[:300]}')

        # Save
        with open('api_debug.json', 'w', encoding='utf-8') as f:
            json.dump(captured, f, ensure_ascii=False, indent=2)

        page.close()
        context.close()

if __name__ == '__main__':
    main()
