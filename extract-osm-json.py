#!/usr/bin/env python3
"""Extract venues from OSM JSON files."""

import json
import os
import glob

def extract_venue(element):
    """Extract venue from OSM element."""
    tags = element.get('tags', {})

    # Get coordinates
    if element['type'] == 'node':
        lat = element.get('lat')
        lon = element.get('lon')
    elif element['type'] == 'way' and 'center' in element:
        lat = element['center'].get('lat')
        lon = element['center'].get('lon')
    else:
        return None

    name = tags.get('name') or tags.get('name:vi') or tags.get('name:en')
    if not name:
        return None

    # Build address
    street = tags.get('addr:street', '')
    number = tags.get('addr:housenumber', '')
    city = tags.get('addr:city', 'Ho Chi Minh City')

    address = ''
    if number:
        address = f"{number} "
    if street:
        address += street
    if city and 'ho chi minh' not in city.lower():
        address += f", {city}"

    return {
        'id': f'osm-{element["id"]}',
        'name': name,
        'amenity': tags.get('amenity', ''),
        'cuisine': tags.get('cuisine', ''),
        'address': address.strip(),
        'lat': lat,
        'lng': lon,
        'phone': tags.get('phone') or None,
        'opening_hours': tags.get('opening_hours') or None,
        'website': tags.get('website') or None,
        'source': 'osm',
        'sourceId': str(element['id']),
    }

def main():
    all_venues = []

    # Find all OSM region files
    for filepath in sorted(glob.glob('osm_region_*.json')):
        print(f"Processing {filepath}...")
        with open(filepath, encoding='utf-8') as f:
            data = json.load(f)

        elements = data.get('elements', [])
        for elem in elements:
            venue = extract_venue(elem)
            if venue:
                all_venues.append(venue)

        print(f"  Extracted {len(elements)} elements")

    print(f"\nTotal venues extracted: {len(all_venues)}")

    # Remove duplicates by ID
    seen = set()
    unique = []
    for v in all_venues:
        if v['id'] not in seen:
            seen.add(v['id'])
            unique.append(v)

    print(f"After deduplication: {len(unique)} venues")

    # Statistics
    amenities = {}
    for v in unique:
        a = v['amenity'] or 'unknown'
        amenities[a] = amenities.get(a, 0) + 1

    print("\nAmenity breakdown:")
    for a, c in sorted(amenities.items(), key=lambda x: -x[1]):
        print(f"  {a}: {c}")

    # Save
    with open('osm-hcm-restaurants.json', 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print("\nSaved to osm-hcm-restaurants.json")

if __name__ == '__main__':
    main()
