import json

formatted_filename = "speed_cameras_all_formatted.json"
geojson_filename = "nz_speed_cameras_geojson.json"

with open(formatted_filename, encoding="utf-8") as f:
    data = json.load(f)

geojson = {
    "type": "FeatureCollection",
    "features": []
}

for item in data['cams']:
    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [item['lng'], item['lat']]
        },
        "properties": {}
    }
    for k, v in item.items():
        if k not in ["lng", "lat"]:
            feature['properties'][k] = v
    geojson['features'].append(feature)

with open(geojson_filename, "w+", encoding="utf-8") as f:
    json.dump(geojson, f, indent=2, ensure_ascii=False)
