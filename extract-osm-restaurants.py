#!/usr/bin/env python3
"""Extract restaurants from Vietnam OSM PBF file."""

import osmium
import json
import sys
import os

class RestaurantHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.restaurants = []

    def node(self, n):
        if n.location.valid():
            tags = dict(n.tags)
            if tags.get('amenity') in ['restaurant', 'cafe', 'fast_food']:
                self.process_venue(n.id, 'node', n.location.lon, n.location.lat, tags)

    def way(self, w):
        if w.IsClosed() and w.location.valid():
            tags = dict(w.tags)
            if tags.get('amenity') in ['restaurant', 'cafe', 'fast_food']:
                center = w.center()
                self.process_venue(w.id, 'way', center.lon, center.lat, tags)

    def process_venue(self, osm_id, osm_type, lon, lat, tags):
        name = tags.get('name') or tags.get('name:vi') or tags.get('name:en')
        if not name:
            return

        # HCM bounding box
        if not (10.7 <= lat <= 11.1 and 106.5 <= lon <= 107.0):
            return

        self.restaurants.append({
            'id': f'osm-{osm_id}',
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
            'sourceId': str(osm_id),
        })

def main():
    pbf_file = 'vietnam-latest.osm.pbf'
    if not os.path.exists(pbf_file):
        print(f"Error: {pbf_file} not found")
        sys.exit(1)

    print(f"Extracting restaurants from {pbf_file}...")
    handler = RestaurantHandler()
    handler.apply_file(pbf_file, locations=True)

    restaurants = handler.restaurants
    print(f"Found {len(restaurants)} restaurants in HCM")

    # Save
    with open('osm-hcm-restaurants.json', 'w', encoding='utf-8') as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=2)
    print(f"Saved to osm-hcm-restaurants.json")

    # Statistics
    amenities = {}
    for r in restaurants:
        a = r['amenity']
        amenities[a] = amenities.get(a, 0) + 1
    print("\nAmenity breakdown:")
    for a, c in sorted(amenities.items(), key=lambda x: -x[1]):
        print(f"  {a}: {c}")

if __name__ == '__main__':
    main()
