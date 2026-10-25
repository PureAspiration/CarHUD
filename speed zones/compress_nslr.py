import json
import time
from datetime import datetime, timezone

import shapely
from shapely.geometry import shape, MultiPolygon, mapping

# https://speedlimits.nzta.govt.nz/
# https://opendata-nzta.opendata.arcgis.com/datasets/NZTA::national-speed-limit-register-nslr/about

geojson_filepath = "output.geojson"
compressed_geojson_filepath = "compressed_nslr.json"

tolerance = 0.00005
# 0.0001 tol recommended (~ 10 meters), decrease for more precision (more storage, slower processing)
# Set to None for no compression
# Check precision on https://geojson.io/ after generation

exclude_value_for_keys = {
    "rcaZoneReferenceName": [  # Exclude region
        "Chatham Islands Territory"
    ]
}

nslr_keys = {
    "OBJECTID": "OBJECTID",
    "rcaZoneReferenceName": "zoneArea",
    "speedLimitZoneName": "zoneName",
    "speedCategoryName": "category",
    "speedLimitZoneValue": "speedLimit",
    "speedLimitZoneMaxValue": "speedLimitMax",
    "speedLimitZoneMinValue": "speedLimitMin",
    "speedLimitZoneVariableSpeed": "speedLimitVar",
    "speedLimitZoneReasonName": "zoneReason",
    "speedLimitZoneDesc": "zoneDesc",
    "speedLimitZoneStartDate": "zoneStartDate",
    "speedLimitZoneEndDate": "zoneEndDate",
    "whenEffective": "zoneEffectiveDate",
    "whenIneffective": "zoneIneffectiveDate",
    "Shape__Area": "area",
    "actualArea": "actualArea"
}

remove_reason = {
    "nodata": 0,
    "matchkeys": 0,
    "outdated": 0
}


def iso_string_to_timestamp(date_string):
    dt = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")
    dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


# Open and load data
start = time.time()
print("Loading GEOJSON...")
with open(geojson_filepath, encoding="utf-8") as geojson_file:
    geojson_raw = json.load(geojson_file)
    del geojson_file
print(f"Done loading GEOJSON ({time.time() - start}s).")

start = time.time()
print("Starting compression...")
remove_records = []
_timings = {}
_total_records = len(geojson_raw['features'])
_last_percent = -1
for i, record in enumerate(geojson_raw['features']):
    _percent = round((i / _total_records) * 100)
    if _percent != _last_percent:
        print(f"Compressing {i}/{_total_records} records... ({_percent}% complete)")
        _last_percent = _percent

    # Gets records with no geometry data ready for deletion
    if record['geometry'] is None:
        remove_records.append(record)
        remove_reason['nodata'] += 1
        continue

    # Removes records with matched values for specific keys
    for key, exclude_values in exclude_value_for_keys.items():
        if record['properties'][key] in exclude_values:
            remove_records.append(record)
            remove_reason['matchkeys'] += 1
            continue

    # Remove records that are outdated
    end_date = record['properties'].get('speedLimitZoneEndDate')
    ineffective_date = record['properties'].get('whenIneffective')
    if (end_date and iso_string_to_timestamp(end_date) < time.time() - 31536000) or (ineffective_date and iso_string_to_timestamp(ineffective_date) < time.time() - 31536000):
        remove_records.append(record)
        remove_reason['outdated'] += 1
        continue

    # Simplify polygon geometries
    if tolerance is not None:
        task_start = time.time()
        polygon: MultiPolygon = shape(record["geometry"])
        geojson_raw['features'][i]['properties']['actualArea'] = shapely.area(polygon)
        simplified_polygon = polygon.simplify(tolerance, preserve_topology=True)
        del polygon
        simplified_geojson_geom = mapping(simplified_polygon)
        del simplified_polygon
        geojson_raw["features"][i]["geometry"] = simplified_geojson_geom
        del simplified_geojson_geom
        _timings["simplify"] = _timings.get("simplify", []) + [time.time() - task_start]

    # Deletes unused keys and renames keys
    task_start = time.time()
    for k, v in record['properties'].items():
        new_properties = record['properties'].copy()
        if k not in nslr_keys.keys():
            del new_properties[k]
        elif k != nslr_keys[k]:
            new_properties[nslr_keys[k]] = v
            del new_properties[k]
        geojson_raw['features'][i]['properties'] = new_properties
    _timings["delete_keys"] = _timings.get("delete_keys", []) + [time.time() - task_start]

time_taken = time.time() - start
print(f"Done compression. ({time_taken}s).")
print(f"Average compression time per record: {time_taken / (_total_records - len(remove_records))}s")
for k, v in _timings.items():
    print(f"Average time to complete \"{k}\" per record: {sum(v) / len(v)}s")

# Delete records with no geometry data or outdated
start = time.time()
print(remove_reason)
print(f"Removing {len(remove_records)} unused records...")
for remove_item in remove_records:
    geojson_raw['features'].remove(remove_item)
print(f"Done removing useless geometries ({time.time() - start}s).")

# Format
start = time.time()
print("Formatting...")
geojson_compressed = json.dumps(geojson_raw, indent=1)  # Keep indent 1 for low storage
del geojson_raw
print(f"Done formatting GEOJSON ({time.time() - start}s).")

# Write
start = time.time()
print("Writing...")
with open(compressed_geojson_filepath, mode="w+") as new_geojson_file:
    new_geojson_file.write(geojson_compressed)
del geojson_compressed
print(f"Done writing ({time.time() - start}s).")
