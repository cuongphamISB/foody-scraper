#!/usr/bin/env python3
"""
Merge Foody data from multiple sources
"""
import json
from pathlib import Path

OUTPUT_DIR = Path('data/foody-full')

def merge_foody_data():
    """Merge all foody data sources"""
    all_venues = []
    seen_ids = set()
    scraped_pages = set()

    # Load progress.json (main data from scraper)
    progress_file = OUTPUT_DIR / 'progress.json'
    if progress_file.exists():
        with open(progress_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for v in data.get('venues', []):
                vid = v.get('id')
                if vid and vid not in seen_ids:
                    seen_ids.add(vid)
                    all_venues.append(v)
            scraped_pages.update(data.get('scraped_pages', []))
        print(f'From progress.json: {len(data.get("venues", []))} venues')

    # Load backfill.json
    backfill_file = OUTPUT_DIR / 'foody_backfill.json'
    if backfill_file.exists():
        with open(backfill_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            added = 0
            for v in data.get('venues', []):
                vid = v.get('id')
                if vid and vid not in seen_ids:
                    seen_ids.add(vid)
                    all_venues.append(v)
                    added += 1
            print(f'From backfill: {added} new venues')

    # Load any other foody files
    for f in OUTPUT_DIR.glob('foody_*.json'):
        if f.name in ['progress.json', 'foody_full.json', 'foody_backfill.json']:
            continue
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                venues = data.get('venues', data) if isinstance(data, dict) else data
                if isinstance(venues, list):
                    added = 0
                    for v in venues:
                        vid = v.get('id')
                        if vid and vid not in seen_ids:
                            seen_ids.add(vid)
                            all_venues.append(v)
                            added += 1
                    if added > 0:
                        print(f'From {f.name}: {added} new venues')
        except Exception as e:
            print(f'Skipping {f.name}: {e}')

    # Sort by id
    all_venues.sort(key=lambda x: x.get('id', ''))

    # Save merged
    output = OUTPUT_DIR / 'foody_merged.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': all_venues,
            'total': len(all_venues),
            'merged_at': '2026-08-24'
        }, f, ensure_ascii=False, indent=2)

    print()
    print(f'Total merged: {len(all_venues)} venues')
    print(f'Saved to: {output}')

    # Also update foody_full.json
    full_output = OUTPUT_DIR / 'foody_full.json'
    with open(full_output, 'w', encoding='utf-8') as f:
        json.dump({
            'venues': all_venues,
            'total': len(all_venues),
            'source': 'foody.vn',
            'updated_at': '2026-08-24'
        }, f, ensure_ascii=False, indent=2)

    print(f'Updated: {full_output}')

if __name__ == '__main__':
    merge_foody_data()
