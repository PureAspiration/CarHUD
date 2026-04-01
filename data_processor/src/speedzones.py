import json
import math
from datetime import datetime, timezone, timedelta, time as dt_time

from shapely.geometry import Point, shape


def dist_from_deg(decimal_degrees: float, latitude: float):
    # This function only approximates distances and is not accurate over long distances.
    return decimal_degrees * (40075016.7 / 360) * math.cos(latitude * (math.pi / 180))


def date_str_to_datetime(date_str: str, local_timezone):
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=timezone.utc).astimezone(local_timezone)
    except ValueError:
        return datetime.strptime(date_str[:-4], "%a, %d %b %Y %H:%M:%S").replace(tzinfo=timezone.utc).astimezone(local_timezone)


class SpeedZoneData:
    def __init__(self, grid_folder):
        self.grid_folder = grid_folder
        with open(f"{grid_folder}/pointer.json", encoding="utf-8") as f:
            self.pointer = json.load(f)

    def get_most_appropriate_zone(self, longitude: float, latitude: float, current_date: datetime, local_timezone, max_dist: float = 10):
        nearby_speed_data = self.get_nearby_speed_zones(longitude, latitude, max_dist)
        # print(f"SPEED DATA ({len(nearby_speed_data)}): {nearby_speed_data}")
        # for item in nearby_speed_data:
        #     print(item)
        return self.choose_best_zone(nearby_speed_data, current_date, local_timezone)

    def get_cell_data_at_point(self, point: Point):
        for cell_filename, polygon in self.pointer['pointer'].items():
            if point.within(shape(polygon)):
                try:
                    with open(f"{self.grid_folder}/{cell_filename}.json", encoding="utf-8") as geojson_file:
                        cell_geojson = json.load(geojson_file)
                        # print(f"Found cell file: {cell_filename}.json")
                        return cell_geojson
                except FileNotFoundError:
                    print("Pointed file was not found.")
        return None

    def get_nearby_speed_zones(self, longitude: float, latitude: float, max_dist: float):
        zones = []
        location = Point(longitude, latitude)

        cell_geojson = self.get_cell_data_at_point(location)

        if cell_geojson is None:
            print("Out of data range.")
            return zones

        for item in cell_geojson['features']:
            area_polygon = shape(item['geometry'])
            properties = item['properties'].copy()

            distance = location.distance(area_polygon)
            distance_meters = round(dist_from_deg(distance, latitude), 1)
            if 0 <= distance_meters < max_dist:
                zones.append({
                    "properties": properties.copy(),
                    "distance": distance_meters,
                    "shape": area_polygon
                })

        return zones

    @staticmethod
    def is_zone_currently_effective(zone_properties: dict, current_date: datetime, local_timezone) -> (bool, bool):
        start_date = date_str_to_datetime(zone_properties['zoneEffectiveDate'], local_timezone)
        end_date = zone_properties['zoneIneffectiveDate']
        if end_date:
            end_date = date_str_to_datetime(zone_properties['zoneIneffectiveDate'], local_timezone)
        else:
            end_date = (datetime.max - timedelta(days=1)).replace(tzinfo=timezone.utc).astimezone(local_timezone)

        speed_lim_start_date = date_str_to_datetime(zone_properties['zoneStartDate'], local_timezone)
        speed_lim_end_date = zone_properties['zoneEndDate']
        if speed_lim_end_date:
            speed_lim_end_date = date_str_to_datetime(zone_properties['zoneEndDate'], local_timezone)
        else:
            speed_lim_end_date = (datetime.max - timedelta(days=1)).replace(tzinfo=timezone.utc).astimezone(local_timezone)  # minus one day and prevents OverflowError

        # Returns: effective: bool, speed limit effective: bool
        return start_date <= current_date <= end_date, speed_lim_start_date <= current_date <= speed_lim_end_date

    def choose_best_zone(self, data, current_date: datetime, local_timezone):
        if not data:
            return None
        if len(data) == 1:
            return data[0]  # Return only available zone

        # Filter to only currently effective zones
        effective_zones = []
        unconfident_effective_zones = []
        for item in data:
            effective, speed_lim_effective = self.is_zone_currently_effective(item['properties'], current_date, local_timezone)
            if speed_lim_effective:
                effective_zones.append(item)  # Prioritizes speed limit date range
            elif effective:
                unconfident_effective_zones.append(item)
        if not effective_zones:
            # print("Using unconfident effective zones")
            effective_zones = unconfident_effective_zones  # Use unconfident zones if no effective zones
        if not effective_zones:
            # print("No effective zones found, ignoring effectiveness and checking all")
            effective_zones = data  # If still no zones, ignore effective or not and use
        if len(effective_zones) == 1:
            return effective_zones[0]  # Return only effective zone and only get info (not distance)

        # print(f"CHOSEN EFFECTIVE ZONES ({len(effective_zones)}): {effective_zones}")
        # for item in effective_zones:
        #     print(item)

        all_zone_areas = [zone['properties']['actualArea'] for zone in effective_zones]
        min_area = min(all_zone_areas)
        max_area = min(max(all_zone_areas), 1000000)  # Cap the maximum area to 1 million to not affect the range and put larger numbers into small
        size_threshold = 0.1
        size_categories = {
            "small": [zone for zone in effective_zones if zone['properties']['actualArea'] <= min_area + (max_area - min_area) * size_threshold],  # If area <= min + 0.1 range
            "large": [zone for zone in effective_zones if zone['properties']['actualArea'] > min_area + (max_area - min_area) * size_threshold]  # If area > min + 0.1 range
        }
        # print(f"SIZE CATEGORY ({len(size_categories['small'])}/{len(size_categories['large'])}): {size_categories}")
        # for size_category in ['small', 'large']:
        #     print(size_category)
        #     for item in size_categories[size_category]:
        #         print(item['properties']['actualArea'])

        # print("    SMALL:")
        # for item in size_categories['small']:
        #     print(item)
        # print("    LARGE:")
        # for item in size_categories['large']:
        #     print(item)

        category_sort_order = ["Temporary", "Seasonal", "Variable", "Permanent"]
        for size_category in ['small', 'large']:
            if size_categories[size_category]:
                sorted_zones = sorted(size_categories[size_category], key=lambda zone: category_sort_order.index(zone['properties']['category']))
                # print(f"CHOSEN SIZE: {size_category}")
                # print(f"SORTED ZONES ({len(sorted_zones)}): {sorted_zones}")
                # for item in sorted_zones:
                #     print(item)
                return sorted_zones[0]  # Get top result for sorted_zones
        return None

    @staticmethod
    def get_speed_limit_at_zone(zone_properties: dict, current_date: datetime):
        speed_category = zone_properties['category']  # Can be: Permanent, Variable, Seasonal, or Temporary
        speed_zone_reason = zone_properties['zoneReason']  # List of reasons

        # speed_limit is None if it cannot be parsed or there is no data
        try:
            speed_limit = int(zone_properties['speedLimit']) or None
        except ValueError:  # Should never be None
            speed_limit = None

        speed_limit_info = {
            "limit": speed_limit,
            "vary": None,
            "limit_reduced_reason": None
        }

        # If zone is not variable (i.e. temporary, seasonal, permanent), then speed_limit_str is not affected
        # If zone is variable then...
        if speed_category == "Variable":
            # Max speed and min speed will not match only if category is variable.

            # max_speed will fall back to normal speed limit if parsing error or no data
            try:
                max_speed = int(zone_properties.get('speedLimitZoneMaxValue', speed_limit)) or speed_limit
            except ValueError:  # Should never happen
                max_speed = speed_limit

            # min_speed will fall back to max_speed if parsing error or no data
            try:
                min_speed = int(zone_properties.get('speedLimitZoneMinValue', max_speed))
            except ValueError:
                min_speed = max_speed

            # speedLimitZoneVariableSpeed should rarely be None. speedLimitZoneVariableSpeed has data when category is Variable.
            var_speeds = zone_properties.get('speedLimitZoneVariableSpeed', None) or None  # Can be None if data empty

            if var_speeds is not None:  # Variable speeds are listed
                try:
                    var_speeds = list(map(int, str(var_speeds).split(",")))
                    var_speeds = list(sorted(set(var_speeds + [speed_limit, max_speed, min_speed])))  # Removes duplicate speeds and includes limits if not already in list
                    speed_limit_info['vary'] = var_speeds
                    if (speed_zone_reason == "The presence of a school" and
                            (0 <= current_date.weekday() <= 4) and
                            (dt_time(8, 30) <= current_date.time() <= dt_time(9, 15) or
                             dt_time(14, 30) <= current_date.time() <= dt_time(15, 30))):
                        speed_limit = min_speed
                        speed_limit_info['limit_reduced_reason'] = "due to school start/end"
                except ValueError:  # Should never happen
                    speed_limit_info['limit_reduced_reason'] = "Variable speeds could not be parsed: {var_speeds})"
            # If var_speeds is None, then use normal speed limit

        if speed_zone_reason == "The presence of a school":
            zone_properties['zoneReason'] = "School Zone"

        speed_limit_info['limit'] = speed_limit
        return speed_limit_info
