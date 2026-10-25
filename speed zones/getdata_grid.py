"""
Grid-based Approach:
Divide your geographical area into a grid of smaller cells.
Preprocess your coordinates by assigning them to the
appropriate grid cells.
When querying, only check the coordinates within the grid cells
that intersect with the queried area.

This file gets data from the grid folder.
"""

import json
import math
import os
import random
import psutil
import time
import traceback
from datetime import datetime, timezone

from shapely.errors import GEOSException
from shapely.geometry import Point, shape

# https://opendata-nzta.opendata.arcgis.com/datasets/NZTA::national-speed-limit-register-nslr/
# https://speedlimits.nzta.govt.nz/
# https://geojson.io/


grid_folder = "grid"


def get_memory():
    print(f"Memory usage: {psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2} MB")


def dist_from_deg(decimal_degrees: float, latitude: float):
    return decimal_degrees * (40075016.7 / 360) * math.cos(latitude * (math.pi / 180))


def find_cell(point: Point, pointer: dict):
    for cell, polygon in pointer.items():
        if point.within(shape(polygon)):
            return cell
    return None


def get_data_from_coordinates(longitude, latitude):
    a = time.time()
    point = Point(longitude, latitude)
    cell = find_cell(point, pointer['pointer'])
    print(f"Done finding cell ({time.time() - a}s).")

    if cell is None:
        print("Out of data range.")
        # raise ValueError("Out of data range.")
        return

    try:
        a = time.time()
        with open(f"{grid_folder}/{cell}.json", encoding="utf-8") as geojson_file:
            cell_geojson = json.load(geojson_file)
        del geojson_file
        get_memory()
        print(f"Done loading GEOJSON ({time.time() - a}s).")
    except FileNotFoundError:
        print("Out of grid range.")
        # raise ValueError("Out of grid range.")
        return

    a = time.time()
    minimum_distance = float("inf")
    closest_feature = None

    for i, item in enumerate(cell_geojson['features']):
        # print(f"checking {i}")
        if item['geometry'] is None:
            print(f"Geometry none: obj id {item['properties']['OBJECTID']}")
            continue
        else:
            polygon = shape(item['geometry'])
            properties = item['properties'].copy()

            try:
                is_within = point.within(polygon)
                if is_within:
                    print(f"Point is within: \n{properties}")
                    minimum_distance = 0
                    closest_feature = properties.copy()
                elif minimum_distance != 0:
                    distance = point.distance(polygon)
                    if distance < minimum_distance and distance < 0.0005:  # dist less than ~ 50 meters
                        if distance == 0:
                            print(f"Point is within: \n{properties}")
                        minimum_distance = distance
                        closest_feature = properties.copy()
                del polygon, item
            except GEOSException as exception:
                print(f"Error checking within range: GEOSException {exception}")
                continue

    if minimum_distance != 0:
        print("Point is not within any polygon.")
        print(f"Closest polygon is {round(minimum_distance, 4)}° ({round(dist_from_deg(minimum_distance, latitude), 2)}m) away: \n{closest_feature}")

    del point, cell_geojson
    print(f"Done searching. ({time.time() - a}s).")


if __name__ == "__main__":
    get_memory()

    a = time.time()
    print("Setting up...")
    with open(f"{grid_folder}/pointer.json", encoding="utf-8") as pointer_file:
        pointer = json.load(pointer_file)
    del pointer_file
    print(f"Done loading pointer ({time.time() - a}s).")
    get_memory()

    while True:
        start = time.time()
        try:
            cmd = input("Coordinates mode (lat, long): ")
            if cmd.strip() == "":
                continue

            if cmd.strip() in ["exec", "execute", "e"]:
                cmd = input("Execute command > ")
                start = time.time()
                exec(cmd)
            if cmd.strip() == "test":
                while True:
                    try:
                        lat_min = -52.6
                        lat_max = -29.2
                        lon_min = 166.5
                        lon_max = 179.1
                        precision = 7
                        lat = round(random.uniform(lat_min, lat_max), precision)
                        lon = round(random.uniform(lon_min, lon_max), precision)
                        current_date = datetime(random.randint(2015, 2024), random.randint(1, 12), random.randint(1, 28), random.randint(0, 23), random.randint(0, 59)).replace(tzinfo=timezone.utc)
                        print("============================")
                        print(f"testing {lat}, {lon}")
                        get_data_from_coordinates(lon, lat)
                        time.sleep(0.1)
                    except KeyboardInterrupt:
                        break
                print("ENDED TEST")
            else:
                start = time.time()
                latitude, longitude = map(float, cmd.strip().split(", "))

                get_data_from_coordinates(longitude, latitude)

        except Exception as exception:
            print(f"Error occurred when trying to execute command: {exception}")
            traceback.print_exc()

        print("============================")
        get_memory()
        print(f"Command executed in ({time.time() - start}s).")
