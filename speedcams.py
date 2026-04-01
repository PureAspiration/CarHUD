import json
import math

from shapely.geometry import Point


def dist_from_deg(decimal_degrees: float, latitude: float):
    return decimal_degrees * (40075016.7 / 360) * math.cos(latitude * (math.pi / 180))


class SpeedCameraData:
    def __init__(self, filename):
        with open(filename, encoding="utf-8") as f:
            self.speed_camera_data = json.load(f)

    def get_speed_cameras_in_range(self, longitude: float, latitude: float, max_dist: float = 500, camera_list: list = None):
        closest_cams = []
        location = Point(longitude, latitude)
        if camera_list is None:
            camera_list = self.speed_camera_data['features']

        for item in camera_list:
            speed_camera_point = Point(item['geometry']['coordinates'])
            item = item.copy()

            distance = location.distance(speed_camera_point)
            distance_meters = round(dist_from_deg(distance, latitude), 1)
            if 0 <= distance_meters < max_dist:
                item['distance'] = distance_meters
                closest_cams.append(item.copy())

        return closest_cams
