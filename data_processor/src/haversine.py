import numpy as np
from shapely import Point


def distance(p1: Point, p2: Point):
    """
    Calculate the distance between two points in meters using the haversine function.
    :param p1: Point 1
    :param p2: Point 2
    :return: Distance in meters
    """
    return haversine(p1.y, p1.x, p2.y, p2.x) * 1000


def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance in kilometers between two points
    on the earth (specified in decimal degrees)
    """
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = np.sin(d_lat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(d_lon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    km = 6378.137 * c  # Radius of earth in kilometers.
    return km
