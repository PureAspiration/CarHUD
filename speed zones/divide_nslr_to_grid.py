"""
Repeated Grid-based Approach:
Divide your geographical area into a grid of smaller cells.
Cells with too much data would be split again into even smaller cells.
When querying, only check the coordinates within the grid cells
that intersect with the queried area.

This file generates the grid folder.
"""

import json
import math
import time
import os
from shapely.geometry import shape, MultiPolygon, Polygon, mapping

geojson_filepath = "compressed_nslr.json"

max_cell_size = 1
max_cell_file_size = 0.5

cwd = os.path.abspath(os.getcwd())
print(cwd)
if not os.path.exists(f"{cwd}\\grid"):
    os.makedirs(f"{cwd}\\grid")

# Open and load data
start = time.time()
print("Loading GEOJSON...")
with open(geojson_filepath, encoding="utf-8") as geojson_file:
    geojson_raw = json.load(geojson_file)
print(f"Done loading GEOJSON ({time.time() - start}s).")

print("Starting separation...")
print("Determining grid size...")

pointer = {
    "grid_size": max_cell_size,
    "grid_bbox": None,
    "pointer": {}
}

base_grid_geojson = {
    "type": "FeatureCollection",
    "name": f"Total",
    "crs": {},
    "features": []
}


def split_to_grid(geojson_data, cell_size):
    start = time.time()
    bbox = shape(geojson_data['features'][0]['geometry']).bounds
    for feature in geojson_data['features'][1:]:
        geom = shape(feature['geometry'])
        bbox = (
            min(bbox[0], geom.bounds[0]),
            min(bbox[1], geom.bounds[1]),
            max(bbox[2], geom.bounds[2]),
            max(bbox[3], geom.bounds[3])
        )
    print(f"bbox: {bbox}")
    bbox_length, bbox_height = abs(bbox[2] - bbox[0]), abs(bbox[3] - bbox[1])
    print(f"bbox size: {bbox_length}, {bbox_height}")
    grid_rows = math.ceil(bbox_height / cell_size)
    grid_columns = math.ceil(bbox_length / cell_size)
    print(f"rows: {grid_rows}, columns: {grid_columns}, num files: {grid_rows * grid_columns}")
    print(f"Done determining grid size ({time.time() - start}s).")

    start = time.time()
    for row in range(grid_rows):
        for col in range(grid_columns):
            cell_bbox = (
                bbox[0] + (col * cell_size),
                bbox[1] + (row * cell_size),
                min((bbox[0] + (col * cell_size) + cell_size), bbox[2]),
                min((bbox[1] + (row * cell_size) + cell_size), bbox[3])
            )
            cell_polygon = Polygon([
                (cell_bbox[0], cell_bbox[1]),
                (cell_bbox[2], cell_bbox[1]),
                (cell_bbox[2], cell_bbox[3]),
                (cell_bbox[0], cell_bbox[3])
            ])
            cell_name = f"grid_{cell_bbox[0]:.6f}_{cell_bbox[1]:.6f}"
            print(f"Finding intersects of row {row}, col {col} ({cell_name}) // {row * grid_columns + (col + 1)}/{grid_rows * grid_columns} ({(((row * grid_columns + (col + 1)) / (grid_rows * grid_columns)) * 100):.2f}%)")
            cell_geojson = {
                "type": "FeatureCollection",
                "name": cell_name,
                "crs": {},
                "features": []
            }
            # Check for features in the area
            for feature in geojson_data['features']:
                feature_shape: MultiPolygon = shape(feature['geometry'])
                feature_shape = feature_shape.buffer(0)  # Buffer fixes invalid geometries
                intersection: MultiPolygon = cell_polygon.intersection(feature_shape)
                if not intersection.is_empty:
                    cell_geojson['features'].append({
                        "type": "Feature",
                        "properties": feature['properties'].copy(),
                        "geometry": mapping(intersection)
                    })
            # Save file
            if cell_geojson['features']:  # If there is data in the file, then save
                json_string = json.dumps(cell_geojson, indent=1)
                file_size = len(json_string.encode("utf-8")) / (1024 * 1024)
                print(f"Size of {cell_name} is expected to be {file_size:.2f} MB")
                if file_size > max_cell_file_size:
                    print(f"Size of cell over {max_cell_file_size} MB, splitting into smaller cells...")
                    split_to_grid(cell_geojson, cell_size / 2)
                else:  # Data is small enough to save
                    # Save to pointer
                    pointer['pointer'][cell_name] = mapping(cell_polygon)
                    # Save cell data file
                    with open(f"grid/{cell_name}.json", mode="w+") as cell_file:
                        cell_file.write(json_string)
                    # For checking grid only
                    base_grid_geojson['features'].append({
                        "type": "Feature",
                        "properties": {
                            "name": cell_name
                        },
                        "geometry": mapping(cell_polygon)
                    })
    print(f"Done generating grid files ({time.time() - start}s).")
    return bbox


grid_bbox = split_to_grid(geojson_raw, max_cell_size)
pointer['grid_bbox'] = grid_bbox

start = time.time()

# For checking grid only
with open("grid/base_grid.json", mode="w+") as total_file:
    total_file.write(json.dumps(base_grid_geojson, indent=2))
# ----END---- For checking grid only ----END----

with open(f"grid/pointer.json", mode="w+") as cell_file:
    cell_file.write(json.dumps(pointer, indent=2))

print(f"Done writing pointer file ({time.time() - start}s).")
