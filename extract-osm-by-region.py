#!/usr/bin/env python3
"""Extract restaurants from OSM Overpass API by region chunks."""

import json
import time
import requests

def query_osm_region(south, west, north, east):
    """Query Overpass API for a bounding box region."""
    query = f"""[out:json][timeout:60];
(
  node["amenity"="restaurant"]({south},{west},{north},{east});
  way["amenity"="restaurant"]({south},{west},{north},{east});
  node["amenity"="cafe"]({south},{west},{north},{east});
  way["amenity"="cafe"]({south},{west},{north},{east});
);
out center;
"""
    response = requests.post(
        "https://overpass.openstreetmap.fr/api/interpreter",
        data={"data": query},
        headers={"User-Agent": "Mozilla/5.0 (compatible; GateroBot/1.0)"},
        timeout=120
    )
    response.raise_for_status()
    return response.json()

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

    return {
        'id': f'osm-{element["id"]}',
        'name': name,
        'amenity': tags.get('amenity', ''),
        'cuisine': tags.get('cuisine', ''),
        'address': tags.get('addr:street', ''),
        'housenumber': tags.get('addr:housenumber', ''),
        'city': tags.get('addr:city', 'Ho Chi Minh City'),
        'lat': lat,
        'lng': lon,
        'phone': tags.get('phone', ''),
        'opening_hours': tags.get('opening_hours', ''),
        'website': tags.get('website', ''),
        'source': 'osm',
        'sourceId': str(element['id']),
    }

def main():
    # HCM bounding box: 10.7-11.1, 106.5-107.0
    # Split into 3x3 grid
    lat_steps = [10.7, 10.83, 10.97, 11.1]
    lon_steps = [106.5, 106.67, 106.83, 107.0]

    all_venues = []

    for i in range(3):
        for j in range(3):
            south = lat_steps[i]
            north = lat_steps[i+1]
            west = lon_steps[j]
            east = lon_steps[j+1]

            print(f"Querying region ({i},{j}): {south:.2f},{west:.2f} to {north:.2f},{east:.2f}")

            try:
                data = query_osm_region(south, west, north, east)
                elements = data.get('elements', [])
                print(f"  Found {len(elements)} elements")

                for elem in elements:
                    venue = extract_venue(elem)
                    if venue:
                        all_venues.append(venue)

                time.sleep(2)  # Be nice to Overpass API

            except Exception as e:
                print(f"  Error: {e}")
                continue

    print(f"\nTotal venues extracted: {len(all_venues)}")

    # Remove duplicates by ID
    seen = set()
    unique = []
    for v in all_venues:
        if v['id'] not in seen:
            seen.add(v['id'])
            unique.append(v)

    print(f"After deduplication: {len(unique)} venues")

    # Save
    with open('osm-hcm-restaurants.json', 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print("Saved to osm-hcm-restaurants.json")

    # Statistics
    amenities = {}
    for v in unique:
        a = v['amenity']
        amenities[a] = amenities.get(a, 0) + 1
    print("\nAmenity breakdown:")
    for a, c in sorted(amenities.items(), key=lambda x: -x[1]):
        print(f"  {a}: {c}")

if __name__ == '__main__':
    main()
