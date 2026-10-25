import copy
import logging
import logging.handlers
import multiprocessing
import os
import socket
import threading
import time
import traceback
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone, date as dt_date, time as dt_time
from typing import TYPE_CHECKING
from typing import Union, Dict, Any

if TYPE_CHECKING:
    import obd

import numpy as np
import psutil
import pynmea2
import pytz
import serial
from shapely import LineString
from shapely.geometry import Point

from haversine import haversine, distance
from speedcams import SpeedCameraData
from speedzones import SpeedZoneData

# from luma.core.render import canvas

# GPS Serial connection
gps_port = "/dev/ttyS3"
gps_baud_rate = 115200
gps_timeout = 5

# ESP32 Serial connection
esp32_port = "/dev/ttyS5"
esp32_baud_rate = 115200
esp32_timeout = 1

# OBD Serial connection
obd_port = "/dev/rfcomm0"
obd_baud_rate = 9600

# TESTING: Fake playback speed
# This feature will multiply the speed and slow down time
playback_multiplier = 1  # Playback speed of 1 is normal

# Data files
speed_camera_filename = "nz_speed_cameras_geojson.json"
speed_limit_grid_folder = "grid"

# https://gist.github.com/tschaub/cc70281ce4df5358eac38b34409b9ef9
last_timezone_update = None
local_timezone = pytz.timezone("Pacific/Auckland")  # todo change timezone dynamically

# GPS Data Processing
zone_upd_freq = 5
cams_passive_upd_freq = 3
cams_active_upd_freq = 0.5
# Other background tasks
wifi_check_freq = 10

# GPS Data
gps_start_time = time.time()
initial_gps_data: Dict[str, Any] = {
    "module_connected": False,
    "failed_attempts": 0,
    "last_response": 0,
    "gps_signal": False,
    "wifi": False,
    "datetime": None,
    "time": None,
    "date": None,
    "latitude": 0,
    "longitude": 0,
    "speed": None,
    "instantaneous_speed": None,
    "average_speed": None,
    "weighted_speed": None,
    "speed_above_5": False,
    "weighted_speed_above_5": False,
    "num_sats": 0,
    "initial_fix_datetime": None,
    "ttff": None
}
gps_stop_event = threading.Event()

initial_obd_data: Dict[str, Any] = {  # This is used to create a multiprocessing dict
    "car_connected": False,
    "failed_attempts": 0,
    "rpm": None,
    "rpm_last_resp_time": None,
    "speed": None,
    "speed_last_resp_time": None,
    "fuel_flow": None,
    "fuel_flow_last_resp_time": None,
    "bat_rem": None,
    "bat_rem_last_resp_time": None
}
obd_stop_event = multiprocessing.Event()

location_history = deque(maxlen=40)
general_location_history = deque(maxlen=40)

speed_history = deque(maxlen=40)
speed_history_queue = multiprocessing.Queue()
speed_prediction = None
speed_prediction_minimum_difference = 2

initial_speed_source = "C"  # W for weighted, G for actual GPS, C for OBD car speed

zone_info: Dict[str, Any] = {
    "next_zone_upd": time.time(),
    "limit": None,
    # "limit_reduced_reason": None,
    "vary": [],
    "category": None,
    "zoneReason": None,
    "zoneName": None,
    "zoneArea": None,
    "shape": None
}

speed_cams_info: Dict[str, Any] = {
    "next_cams_upd": time.time(),
    "monitoring_speed_cams": [],  # Speed cams within a smaller radius
    "nearby_speed_cams": [],  # Speed cams within a larger radius
    "relevant_speed_cam": None,  # Relevant speed cam which should be warned
    "last_nearby_cams_upd_loc": None  # Last larger radius update coordinates
}

prev_zone = {}

last_speed_log = time.time()


# ###########################################
# #####              LOGGING            #####
# ###########################################

def setup_logging(log_queue=None, log_file=None):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('[%(processName)s] %(asctime)s - %(levelname)s - %(message)s')

    # Clear existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # If using a log queue (for workers), replace with queue handler
    if log_queue:
        queue_handler = logging.handlers.QueueHandler(log_queue)
        logger.handlers = [queue_handler]


def log_listener(queue, log_file):
    setup_logging(log_file=log_file)  # Setup console output here
    while True:
        try:
            record = queue.get()
            if record is None:
                break
            logger = logging.getLogger(record.name)
            logger.handle(record)
        except Exception as e:
            logging.error(f"Logging error ({e}):")
            traceback.print_exc()


def worker_init(log_queue):
    setup_logging(log_queue)


# ###########################################
# #####              STATS              #####
# ###########################################

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = round(int(f.read()) / 1000.0)
        return temp
    except FileNotFoundError:
        return None


def get_memory_usage():
    return round(psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2, 1)


# ###########################################
# #####        SPEED CALCULATIONS       #####
# ###########################################

def calculate_speed(lat1, lon1, time1, lat2, lon2, time2):
    distance_travelled = haversine(lat1, lon1, lat2, lon2)
    time_taken_for_distance = abs(time2 - time1)
    if time_taken_for_distance == 0:  # Prevents division by zero
        return None

    return distance_travelled / (time_taken_for_distance / 3600)


def get_closest_timestamp_index(list_of_timestamps, target_timestamp, largest_allowed_dev=2) -> Union[int, None]:
    closest_index = 0
    closest_timestamp = 0
    min_diff = float("inf")
    for i, timestamp in enumerate(list_of_timestamps):
        diff = abs((timestamp - target_timestamp))
        if diff < min_diff:
            min_diff = diff
            closest_index = i
            closest_timestamp = timestamp
    dev = target_timestamp - closest_timestamp
    if dev > largest_allowed_dev:
        return None
    return closest_index


def calculate_instantaneous_speed():
    min_data_time = 1.5
    max_data_time = 3
    speed_threshold = 30

    if len(location_history) < 2:
        return None

    latest_time = location_history[-1][2]

    # Low speed regime
    closest_index = get_closest_timestamp_index([location[2] for location in location_history], latest_time - max_data_time)
    if closest_index is None:  # Speed is invalid (No new data is provided)
        return None
    approx_speed = calculate_speed(*location_history[closest_index], *location_history[-1])
    if approx_speed is None:
        return None
    if approx_speed < speed_threshold:
        return approx_speed

    # High speed regime
    closest_index = get_closest_timestamp_index([location[2] for location in location_history], latest_time - min_data_time)
    if closest_index is None:  # Speed is invalid (No new data is provided)
        return None
    return calculate_speed(*location_history[closest_index], *location_history[-1])


def predict_speed(speed_history, prediction_window_seconds=2.0, prediction_seconds=3.0):
    if len(speed_history) < 2:
        return None  # not enough data

    t_now = speed_history[-1][1]

    recent = [(s, t) for s, t in speed_history if t >= t_now - prediction_window_seconds]

    if len(recent) < 2:
        return None  # still not enough data

    speeds, times = zip(*recent)
    speeds = np.array(speeds, dtype=np.float64)
    times = np.array(times, dtype=np.float64)

    # Linear regression: speed = slope * time + intercept
    slope, intercept = np.polyfit(times, speeds, 1)

    # Predict x seconds ahead
    t_future = t_now + prediction_seconds
    predicted_speed = slope * t_future + intercept

    return predicted_speed


# ###########################################
# ##### LOCATION PARSING AND ALGORITHMS #####
# ###########################################

def process_nmea_data(data):
    global last_speed_log
    try:
        msg = pynmea2.parse(data)
        # logging.debug(repr(msg))
        if hasattr(msg, "timestamp") and hasattr(msg, "datestamp"):
            if isinstance(msg.datestamp, dt_date) and isinstance(msg.timestamp, dt_time):
                datetime_obj = datetime.combine(msg.datestamp, msg.timestamp)
                datetime_obj = datetime_obj.replace(tzinfo=timezone.utc).astimezone(local_timezone)
                gps_data['datetime'] = datetime_obj
                gps_data['time'] = datetime_obj.strftime("%I:%M:%S %p").lstrip("0").lower()
                gps_data['date'] = datetime_obj.strftime('%a %d/%m/%y')
                if gps_data['initial_fix_datetime'] is None:
                    gps_data['initial_fix_datetime'] = datetime_obj
                if playback_multiplier != 1:
                    elapsed_real = gps_data['datetime'] - gps_data['initial_fix_datetime']
                    elapsed_display = elapsed_real / playback_multiplier
                    display_time = gps_data['initial_fix_datetime'] + elapsed_display
                    gps_data['time'] = display_time.strftime("%I:%M:%S %p").lstrip("0").lower()
                    gps_data['date'] = display_time.strftime('%a %d/%m/%y')

            elif None not in [msg.datestamp, msg.timestamp]:
                logging.info(f"{msg.datestamp} - {type(msg.datestamp)}, {msg.timestamp} - {type(msg.timestamp)}")

        if hasattr(msg, "latitude") and hasattr(msg, "longitude"):
            lat, lon = round(msg.latitude, 6), round(msg.longitude, 6)
            if lat not in [None, 0] and lon not in [None, 0]:
                if gps_data['ttff'] is None:
                    gps_data['ttff'] = round(time.time() - gps_start_time)

                # Save location in history
                location_history.append((lat, lon, time.time()))
                append_to_general_location_history(lat, lon, 2)

                # Calculate instantaneous speed
                if speed_source.value == "W":
                    instantaneous_speed = calculate_instantaneous_speed()

                    gps_data['average_speed'] = ((gps_data['average_speed'] or 0) * 3) / 4 + (instantaneous_speed or 0)
                    weighted_speed = gps_data['average_speed'] / 4
                    gps_data['weighted_speed'] = min(weighted_speed if weighted_speed >= 5 or gps_data['weighted_speed_above_5'] else 0, (instantaneous_speed or 0))
                    if speed_source.value == "W":
                        speed_history_queue.put((gps_data['weighted_speed'], time.time()))

                    if (weighted_speed or 0) >= 5:
                        gps_data['weighted_speed_above_5'] = True
                    elif round(weighted_speed or 0) <= 2:
                        gps_data['weighted_speed_above_5'] = False

                # Update location
                gps_data['latitude'] = lat
                gps_data['longitude'] = lon
                gps_data['gps_signal'] = True

                # Request new zone if detected out of current zone
                if zone_info['shape'] and not Point(lon, lat).within(zone_info['shape']):
                    zone_info['next_zone_upd'] = time.time()

                if time.time() > last_speed_log + 1:
                    last_speed_log = time.time()
            else:
                gps_data['gps_signal'] = False
                if time.time() > last_speed_log + 10:
                    last_speed_log = time.time()
                    logging.info("No connection / speed.")

        if hasattr(msg, "spd_over_grnd_kmph") and type(msg.spd_over_grnd_kmph) in [float, int]:
            gps_speed = msg.spd_over_grnd_kmph
            gps_data['speed'] = gps_speed if gps_speed >= 5 or gps_data['speed_above_5'] else 0
            if obd_data['car_connected'] is False or int(gps_data['num_sats']) >= 8:
                if speed_source.value != "G":
                    logging.info(f"Speed source has been changed to GPS as car is not connected, or GPS is reliable ({int(gps_data['num_sats'])} sats).")
                speed_source.value = "G"
                speed_history_queue.put((gps_data['speed'], time.time()))

            if (gps_speed or 0) >= 5:
                gps_data['speed_above_5'] = True
            elif round(gps_speed or 0) <= 2:
                gps_data['speed_above_5'] = False

        if hasattr(msg, "num_sats"):
            gps_data['num_sats'] = msg.num_sats

    except pynmea2.ParseError:
        pass


def append_to_general_location_history(lat: float, lon: float, tolerance_meters: float):
    # Only add if more than x meters away from last point
    if general_location_history:
        prev_lat, prev_lon, _ = general_location_history[-1]
        distance_km = haversine(prev_lat, prev_lon, lat, lon)
        if distance_km < tolerance_meters / 1000:
            return

    general_location_history.append((lat, lon, time.time()))


def update_speed_and_location(longitude: float, latitude: float, current_date: datetime, prev_zone: dict = None):
    # logging.info(f"updating with {longitude}, {latitude}, {current_date}")
    # -36.9099849653591, 174.743496150134

    if prev_zone is None:
        prev_zone = {}
    if "shape" in prev_zone and Point(longitude, latitude).within(prev_zone['shape']):
        logging.info("Using previous geometry.")
        return {}

    speed_zone = speed_zone_data.get_most_appropriate_zone(longitude, latitude, current_date, local_timezone)
    if speed_zone is not None:
        data = speed_zone_data.get_speed_limit_at_zone(speed_zone['properties'], current_date)
        return {
            "limit": data['limit'],
            # "limit_reduced_reason": data['limit_reduced_reason'],  # TODO REMOVE
            "vary": data['vary'],
            "category": speed_zone['properties']['category'],
            "zoneReason": speed_zone['properties']['zoneReason'],
            "zoneName": speed_zone['properties']['zoneName'],
            "zoneArea": speed_zone['properties']['zoneArea'],
            "shape": speed_zone['shape']
        }


def update_speed_cams(longitude: float, latitude: float, speed_cams_info: dict, location_history: deque):
    nearby_speed_cams = speed_cams_info['nearby_speed_cams']
    updated_nearby = False
    # If speed cams have not been updated or last update point is over 250m away
    if speed_cams_info['last_nearby_cams_upd_loc'] is None or distance(speed_cams_info['last_nearby_cams_upd_loc'], Point(longitude, latitude)) > 250:
        nearby_speed_cams = speed_camera_data.get_speed_cameras_in_range(longitude, latitude, 1500)
        updated_nearby = True
    # else:
    #     logging.info(f"Using old list of nearby speed cam`eras as dist < 250m ({distance(speed_cams_info['last_nearby_cams_upd_loc'], Point(longitude, latitude))})")
    monitoring_cams = speed_camera_data.get_speed_cameras_in_range(longitude, latitude, 350, nearby_speed_cams)
    relevant_speedcam = find_relevant_speedcam(location_history, monitoring_cams)
    logging.debug(f"[Cams]: Near: {len(nearby_speed_cams)} Monit: {len(monitoring_cams)} | Relevant: {relevant_speedcam}")
    return nearby_speed_cams, monitoring_cams, relevant_speedcam, Point(longitude, latitude) if updated_nearby is True else None


def get_direction_line(location_history, recent_n=16):
    """Returns a LineString representing direction of travel from recent locations"""
    if len(location_history) < 3:
        return None

    recent = list(location_history)[-recent_n:]
    lat0, lon0 = map(np.radians, recent[0][:2])
    R = 6371000

    xy = []
    for lat, lon, _ in recent:
        lat, lon = np.radians(lat), np.radians(lon)
        dx = (lon - lon0) * np.cos(lat0) * R
        dy = (lat - lat0) * R
        xy.append((dx, dy))
    xy = np.array(xy)

    mean = xy.mean(axis=0)
    U, S, Vt = np.linalg.svd(xy - mean)
    direction = Vt[0]

    # Determine direction of travel (from earliest to latest point)
    travel_vector = xy[-1] - xy[0]
    if np.dot(direction, travel_vector) < 0:
        direction = -direction  # flip to match actual travel direction

    # Extend 350 m forward (direction of travel) and 50 m backward
    forward_len = 350
    backward_len = 50

    pt1 = mean - direction * backward_len
    pt2 = mean + direction * forward_len

    return LineString([pt1, pt2])


def find_relevant_speedcam(location_history, monitoring_cams, max_distance=75):
    """Returns the most relevant speed cam (within distance of direction line)"""
    direction_line = get_direction_line(location_history)
    if direction_line is None:
        return None

    lat0, lon0 = map(np.radians, location_history[0][:2])
    R = 6371000

    # Get most recent location (converted to local x, y)
    latest_lat, latest_lon = map(np.radians, location_history[-1][:2])
    dx_recent = (latest_lon - lon0) * np.cos(lat0) * R
    dy_recent = (latest_lat - lat0) * R
    recent_point = Point(dx_recent, dy_recent)

    closest_cam = None
    closest_dist = float('inf')

    for i, cam in enumerate(monitoring_cams):
        lon, lat = cam['geometry']['coordinates']
        lat, lon = np.radians(lat), np.radians(lon)
        dx = (lon - lon0) * np.cos(lat0) * R
        dy = (lat - lat0) * R
        cam_point = Point(dx, dy)  # Projected to local xy plane in meters

        dist_to_cam = recent_point.distance(cam_point)
        # logging.debug(f"Cam {i}: dist {dist_to_cam}m, lined {direction_line.distance(cam_point)} < {max_distance}")
        if direction_line.distance(cam_point) < max_distance and dist_to_cam < closest_dist:
            closest_dist = dist_to_cam
            closest_cam = cam

    return closest_cam


# ###########################################
# #####               WIFI              #####
# ###########################################

def check_if_wifi_connected():
    try:
        host = socket.gethostbyname("1.1.1.1")
        s = socket.create_connection((host, 80), 1)
        s.close()
        return True
    except OSError:
        pass
    return False


def check_wifi_loop():
    while True:
        gps_data['wifi'] = check_if_wifi_connected()
        # logging.debug(f"Wifi connected: {gps_data['wifi']}")
        time.sleep(wifi_check_freq)


# ###########################################
# #####        GPS Data Receivers       #####
# ###########################################

def gps_sim_receiver():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        HOST = "0.0.0.0"
        PORT = 12543

        s.bind((HOST, PORT))
        s.listen(1)
        logging.debug(f"Listening on {HOST}:{PORT}...")

        conn, addr = s.accept()
        with conn:
            logging.info(f"Connected by {addr}")
            gps_stop_event.set()
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                gps_data['module_connected'] = True
                speed_source.value = "W"
                process_nmea_data(data.decode().strip())


def gps_read_loop(gps_serial):
    while not gps_stop_event.is_set():
        try:
            raw_line = gps_serial.readline()
            if raw_line is None:
                continue
            data = raw_line.decode("utf-8").strip()
            # logging.debug(data)

            if data:
                gps_data['module_connected'] = True
                gps_data['last_response'] = time.time()
                process_nmea_data(data)
                gps_data['failed_attempts'] = 0
            elif (time.time() - gps_data['last_response']) >= 5:
                gps_data['module_connected'] = False

            if gps_serial.in_waiting >= 512:
                logging.warning(f"GPS buffer overflow protection triggered ({gps_serial.in_waiting})")
                gps_serial.reset_input_buffer()

        except UnicodeDecodeError as e:
            logging.warning(f"Unicode decode error: {e} — skipping line.")
            continue
        except serial.SerialException as e:
            logging.debug(f"GPS Port exists?: {os.path.exists(gps_port)}")
            logging.warning(f"Serial error: {e} occurred, reconnecting...")
            gps_data['failed_attempts'] += 1
            time.sleep(1)
            gps_serial.close()
            break  # Break inner loop to reinitialize the serial connection
        except Exception as exception:
            logging.error(f"{exception} occurred in GPS read loop:")
            traceback.print_exc()
            gps_data['module_connected'] = False
            gps_data['gps_signal'] = False
        # time.sleep(0.01)


def gps_reader():
    while not gps_stop_event.is_set():
        try:
            gps_serial = serial.Serial(gps_port, baudrate=gps_baud_rate, timeout=gps_timeout, rtscts=False, dsrdtr=False)
            gps_serial.flush()
            gps_serial.reset_input_buffer()
            gps_serial.reset_output_buffer()
            logging.debug("GPS Serial started")
            gps_read_loop(gps_serial)

        except serial.SerialException:
            logging.warning("Failed to initialize GPS serial connection. Retrying...")
            gps_data['failed_attempts'] += 1
            if gps_data['failed_attempts'] >= 5:
                gps_data['module_connected'] = False
                gps_data['gps_signal'] = False
            time.sleep(1)

        except Exception as exception:
            logging.error(f"{exception} while trying to initialize GPS serial connection:")
            traceback.print_exc()
            gps_data['module_connected'] = False
            gps_data['gps_signal'] = False
            time.sleep(3)


# ###########################################
# #####        OBD Data Receiver        #####
# ###########################################

def obd_retrieve_loop(obd_serial: "obd.OBD", obd_data, gps_data):
    import obd
    from obd import OBDCommand, Unit
    from obd.utils import bytes_to_int
    logging.info("OBD Retrieve Loop started")

    rpm_query_freq = 0
    fuel_flow_query_freq = 0
    speed_query_freq = 0
    hybrid_soc_query_freq = 4

    last_rpm_query = time.time()
    last_fuel_flow_query = time.time()
    last_speed_query = time.time()
    last_hybrid_soc_query = time.time()

    def get_rpm():
        response = obd_serial.query(obd.commands.RPM)
        if response.is_null():
            obd_data['failed_attempts'] += 1
            return None
        else:
            obd_data['car_connected'] = True
            obd_data['failed_attempts'] = 0
            return response.value.magnitude

    def get_speed():
        response = obd_serial.query(obd.commands.SPEED)
        if response.is_null():
            obd_data['failed_attempts'] += 1
            return None
        else:
            obd_data['car_connected'] = True
            obd_data['failed_attempts'] = 0
            return response.value.magnitude

    def get_fuel_flow():
        maf = obd_serial.query(obd.commands.MAF)  # g/s
        if maf.is_null():
            obd_data['failed_attempts'] += 1
            return None

        # long_fuel_trim = obd_serial.query(obd.commands.LONG_FUEL_TRIM_1)
        # if long_fuel_trim.is_null():
        #     obd_data['failed_attempts'] += 1
        #     return None
        #
        # short_fuel_trim = obd_serial.query(obd.commands.SHORT_FUEL_TRIM_1)
        # if short_fuel_trim.is_null():
        #     obd_data['failed_attempts'] += 1
        #     return None

        # fuel_trim = (long_fuel_trim.value.magnitude + short_fuel_trim.value.magnitude) / 100
        # fuel_flow_gpers = maf.value.magnitude / (14.7 * (1 - fuel_trim))  # 14.7 AFR
        fuel_flow_gpers = maf.value.magnitude / 14.7  # 14.7 AFR
        fuel_flow_lperh = (fuel_flow_gpers / 0.745) * 3600 * 0.001  # Fuel density 745 g/L for petrol

        obd_data['failed_attempts'] = 0
        return fuel_flow_lperh

    def hybrid_soc(messages):
        """
        Decoder for Toyota hybrid battery State of Charge
        Expected response: 41 5B XX
        """
        d = messages[0].data  # only operate on a single message
        d = d[2:]  # chop off mode and PID bytes
        raw = bytes_to_int(d)

        soc = (raw * 100.0) / 255.0
        return soc * Unit.percent

    HYBRID_SOC = OBDCommand(
        name="HYBRID_SOC",
        desc="Toyota Hybrid Battery State of Charge",
        command=b"015B",  # Mode 01, PID 5B
        _bytes=3,  # 41 5B XX = 3 bytes
        decoder=hybrid_soc,
    )
    obd_serial.supported_commands.add(HYBRID_SOC)

    def get_hybrid_soc():
        response = obd_serial.query(HYBRID_SOC)
        if response.is_null():
            obd_data['failed_attempts'] += 1
            return None
        else:
            obd_data['car_connected'] = True
            obd_data['failed_attempts'] = 0
            return response.value.magnitude

    while obd_serial.is_connected():
        try:
            if time.time() > last_rpm_query + rpm_query_freq:
                last_rpm_query = time.time()
                response = get_rpm()
                if response is not None:
                    obd_data['rpm'] = response
                    obd_data['rpm_last_resp_time'] = time.time()

            if time.time() > last_fuel_flow_query + fuel_flow_query_freq:
                last_fuel_flow_query = time.time()
                response = get_fuel_flow()
                if response is not None:
                    obd_data['fuel_flow'] = response
                    obd_data['fuel_flow_last_resp_time'] = time.time()

            if time.time() > last_speed_query + speed_query_freq:
                last_speed_query = time.time()
                response = get_speed()
                if response is not None:
                    obd_data['speed'] = response
                    obd_data['speed_last_resp_time'] = time.time()
                    if int(gps_data['num_sats']) <= 7:
                        if speed_source.value != "C":
                            logging.info(f"Speed source has been changed to car as GPS is unreliable ({int(gps_data['num_sats'])} sats).")
                        speed_source.value = "C"  # Speed source to come from car as GPS is unreliable
                        speed_history_queue.put((response, time.time()))
                if int(gps_data['num_sats']) >= 9:
                    speed_query_freq = 2
                else:
                    speed_query_freq = 0

            if time.time() > last_hybrid_soc_query + hybrid_soc_query_freq:
                last_hybrid_soc_query = time.time()
                response = get_hybrid_soc()
                if response is not None:
                    obd_data['bat_rem'] = round(response, 2)
                    obd_data['bat_rem_last_resp_time'] = time.time()

        except Exception as exception:
            logging.error(f"{exception} occurred in OBD read loop:")
            traceback.print_exc()
            obd_data['car_connected'] = False
            break

        if obd_data['failed_attempts'] >= 5:
            logging.warning("Too many failed attempts.")
            break

        time.sleep(0.05)

    logging.warning("Disconnected. Reconnecting in a few seconds...")
    obd_data['car_connected'] = False
    obd_data['failed_attempts'] = 0
    obd_serial.close()

    obd_data['rpm'] = None
    obd_data['speed'] = None
    obd_data['fuel_flow'] = None
    obd_data['bat_rem'] = None

    time.sleep(3)


def obd_data_retriever(obd_data, gps_data):
    # Import here to allow main loop to run faster
    import obd

    time.sleep(1)
    logging.debug("Setting up OBD Serial")
    while not obd_stop_event.is_set():
        # Check if bluetooth port is configured
        if not os.path.exists(obd_port):
            logging.error("RFCOMM does not exist or is not bound.")
            time.sleep(2)
            continue

        # Manual probe connection to ELM and ECU
        # try:
        #     with serial.Serial(obd_port, obd_baud_rate, timeout=1) as ser:
        #         ser.write(b"ATZ\r")
        #         time.sleep(1)
        #         response = ser.read(ser.in_waiting or 128).decode(errors="ignore").strip()
        #         logging.debug(f"ATZ response: {response}")
        #         if "ELM" in response or "OK" in response:
        #             logging.debug("Adapter is connected")
        #         else:
        #             logging.debug("No response from adapter")
        #             time.sleep(5)
        #             continue
        #
        #         ser.write(b"0100\r")
        #         time.sleep(1)
        #         response = ser.read(ser.in_waiting or 128).decode(errors="ignore").strip()
        #         logging.debug(f"0100 response: {response}")
        #         if response and "NO DATA" not in response and response != "?":
        #             logging.debug("Car ECU is responding. Proceeding with OBD connection...")
        #         else:
        #             logging.debug("No response from ECU (car not connected or ignition off).")
        #             time.sleep(2)
        #             continue
        #
        # except serial.SerialException:
        #     logging.warning("Failed to initialize ELM manual serial connection. Retrying...")
        #     time.sleep(1)
        #     continue
        # except Exception as exception:
        #     logging.error(f"{exception} while trying to initialize ELM manual serial connection:")
        #     traceback.print_exc()
        #     time.sleep(5)
        #     continue

        # OBD connection if manual connection works
        try:
            obd_serial = obd.OBD(obd_port, baudrate=obd_baud_rate, fast=True)

            if obd_serial.is_connected():
                logging.debug("OBD Serial is connected to the car")

                obd_retrieve_loop(obd_serial, obd_data, gps_data)
            else:
                logging.warning("OBD Serial is not connected to the car. Retrying soon...")
                obd_data['car_connected'] = False
                time.sleep(5)

        except Exception as exception:
            logging.error(f"{exception} while trying to initialize OBD serial connection:")
            traceback.print_exc()
            obd_data['car_connected'] = False
            time.sleep(5)


# ###########################################
# #####         ESP32 Data Sender       #####
# ###########################################

def remove_invalid_characters(text):
    if not isinstance(text, str):
        return text

    invalid_characters = ["'"]
    for character in invalid_characters:
        text = text.replace(character, "")
    return remove_macrons(text)


def remove_macrons(text):
    if not isinstance(text, str):
        return text

    macron_map = {
        'ā': 'a', 'Ā': 'A',
        'ē': 'e', 'Ē': 'E',
        'ī': 'i', 'Ī': 'I',
        'ō': 'o', 'Ō': 'O',
        'ū': 'u', 'Ū': 'U'
    }
    for macron, plain in macron_map.items():
        text = text.replace(macron, plain)
    return text


def esp32_data_sender():
    while True:
        try:
            esp32_serial = serial.Serial(esp32_port, esp32_baud_rate, timeout=esp32_timeout)

            while True:
                speed_cam_str = "{"
                if speed_cams_info['relevant_speed_cam'] is not None:
                    for k in ["description", "street", "suburb", "location"]:
                        speed_cam_str += f"{k}={speed_cams_info['relevant_speed_cam']['properties'][k]};"
                    speed_cam_str += f"distance={speed_cams_info['relevant_speed_cam']['distance']}"
                speed_cam_str += "}"

                encoded_message = (f"<"
                                   f"ASPD:{speed_history[-1][0] * playback_multiplier if speed_history else -1},"
                                   f"ASPDUPDTIME:{speed_history[-1][1] if speed_history else 0},"
                                   f"SPDSRC:{speed_source.value},"
                                   f"SPDPRD:{speed_prediction * playback_multiplier if speed_prediction is not None else -1},"
                                   # f"WSPD:{gps_data['weighted_speed'] if gps_data['weighted_speed'] is not None else -1},"
                                   # f"GSPD:{gps_data['speed'] if gps_data['speed'] is not None else -1},"
                                   # f"CSPD:{obd_data['speed'] if obd_data['speed'] is not None else -1},"
                                   f"RPM:{obd_data['rpm'] if obd_data['rpm'] is not None else -1},"
                                   f"RPMRESPTIME:{obd_data['rpm_last_resp_time'] if obd_data['rpm_last_resp_time'] is not None else 0},"
                                   f"FUELFLOW:{obd_data['fuel_flow'] if obd_data['fuel_flow'] is not None else -1},"
                                   f"FUELFLOWRESPTIME:{obd_data['fuel_flow_last_resp_time'] if obd_data['fuel_flow_last_resp_time'] is not None else 0},"
                                   f"BATREM:{obd_data['bat_rem'] if obd_data['bat_rem'] is not None else -1},"
                                   f"BATREMRESPTIME:{obd_data['bat_rem_last_resp_time'] if obd_data['bat_rem_last_resp_time'] is not None else 0},"
                                   f"CARCON:{int(obd_data['car_connected'])},"
                                   f"MODCON:{int(gps_data['module_connected'])},"
                                   f"SGNL:{int(gps_data['gps_signal'])},"
                                   f"NUMSATS:{int(gps_data['num_sats'])},"
                                   f"WIFI:{int(gps_data['wifi'])},"
                                   f"TIMESTMP:{time.time()},"
                                   f"TIME:{gps_data['time'] or ''},"
                                   f"DATE:{gps_data['date'] or ''},"
                                   f"LIM:{zone_info['limit'] if zone_info['limit'] is not None else -1}>,"
                                   # f"LIMITREDUCEREASON:{zone_info['limit_reduced_reason']},"
                                   f"VARY:{', '.join(zone_info['vary'] or [])},"
                                   f"CATEGORY:{zone_info['category']},"
                                   f"ZONEREASON:{zone_info['zoneReason']},"
                                   f"ZONENAME:{remove_invalid_characters(zone_info['zoneName'])},"
                                   f"ZONEAREA:{remove_invalid_characters(zone_info['zoneArea'])},"
                                   f"SPEEDCAM:{remove_invalid_characters(speed_cam_str)}"
                                   f">".encode("utf-8"))

                esp32_serial.write(encoded_message)

                time.sleep(0.1)

        except serial.SerialException:
            logging.warning("Failed to initialize ESP32 serial connection. Retrying...")
            time.sleep(1)

        except Exception as exception:
            logging.error(f"{exception} occurred in main thread:")
            traceback.print_exc()
            time.sleep(5)


# ###########################################
# #####             MAIN CODE           #####
# ###########################################

speed_camera_data = SpeedCameraData(speed_camera_filename)
logging.info("Speed camera data set up")
speed_zone_data = SpeedZoneData(speed_limit_grid_folder)
logging.info("Speed zone data set up")

if __name__ == "__main__":
    # Set up logging
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    log_start_time = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = os.path.join(log_dir, f"{log_start_time}.log")

    log_queue = multiprocessing.Queue(-1)
    listener_thread = threading.Thread(target=log_listener, args=(log_queue, log_filename), daemon=True)
    listener_thread.start()
    logging.info("Logging task running")

    # Dict must be down here since multiprocess.Manager must be created after logging setup
    manager = multiprocessing.Manager()
    gps_data = manager.dict(initial_gps_data)
    obd_data = manager.dict(initial_obd_data)
    speed_source = manager.Value(str, initial_speed_source)

    # gps_sim_recv_thread = threading.Thread(target=gps_sim_receiver, daemon=True)
    # gps_sim_recv_thread.start()
    # logging.info("GPS Sim receiver task running")

    gps_reader_thread = threading.Thread(target=gps_reader, daemon=True)
    gps_reader_thread.start()
    logging.info("GPS Serial Read task running")

    obd_data_retriever_thread = multiprocessing.Process(target=obd_data_retriever, args=(obd_data, gps_data), daemon=True, name="OBDRetriever")
    obd_data_retriever_thread.start()
    logging.info("OBD Data Retriever PROCESS running")

    esp32_data_sender_thread = threading.Thread(target=esp32_data_sender, daemon=True)
    esp32_data_sender_thread.start()
    logging.info("ESP32 Data Send task running")

    wifi_thread = threading.Thread(target=check_wifi_loop, daemon=True)
    wifi_thread.start()
    logging.info("Wifi Check task running")

    logging.info("Starting background data fetcher (main thread)")

    # ###########################################
    # #####             MAIN LOOP           #####
    # ###########################################

    future_zone = None
    future_cams = None
    with ProcessPoolExecutor(max_workers=2, initializer=worker_init, initargs=(log_queue,)) as executor:
        while True:
            now = time.time()

            # Get zones and cameras
            if gps_data['longitude'] not in [None, 0] and gps_data['latitude'] not in [None, 0] and gps_data['datetime'] is not None:  # Ensures long/lat data and time available
                # Zone fetcher
                if now > zone_info['next_zone_upd']:
                    if future_zone is None or future_zone.done():
                        logging.info("Fetching zones...")
                        future_zone = executor.submit(update_speed_and_location, gps_data['longitude'], gps_data['latitude'], gps_data['datetime'], copy.deepcopy(prev_zone))
                    else:
                        logging.info("Not fetching zones as previous request has not been completed")


                    def zone_callback(fut):
                        try:
                            result = fut.result()
                            # logging.debug(f"[Main] Zone result: {result}")
                            for key, value in result.items():
                                prev_zone[key] = value
                                zone_info[key] = value
                            # logging.debug(zone_info)
                        except Exception as e:
                            logging.exception(f"[Main] Zone task error: {e}")


                    future_zone.add_done_callback(zone_callback)
                    zone_info['next_zone_upd'] = now + zone_upd_freq

                # Speed camera fetcher
                if now > speed_cams_info['next_cams_upd']:
                    if future_cams is None or future_cams.done():
                        logging.info("Fetching cams...")
                        future_cams = executor.submit(update_speed_cams, gps_data['longitude'], gps_data['latitude'], copy.deepcopy(speed_cams_info), general_location_history.copy())
                    else:
                        logging.info("Not fetching cams as previous request has not been completed")


                    def cams_callback(fut):
                        try:
                            nearby_cams, monitoring_cams, relevant_speedcam, update_location = fut.result()
                            # logging.debug(f"[Main] Cams result: {nearby_cams}, {monitoring_cams}")
                            speed_cams_info['nearby_speed_cams'] = nearby_cams
                            speed_cams_info['monitoring_speed_cams'] = monitoring_cams
                            speed_cams_info['relevant_speed_cam'] = relevant_speedcam
                            if update_location is not None:
                                speed_cams_info['last_nearby_cams_upd_loc'] = update_location
                        except Exception as e:
                            logging.exception(f"[Main] Cams task error: {e}")


                    future_cams.add_done_callback(cams_callback)
                    if speed_cams_info['monitoring_speed_cams']:
                        speed_cams_info['next_cams_upd'] += cams_active_upd_freq
                    else:
                        speed_cams_info['next_cams_upd'] = now + cams_passive_upd_freq

            while not speed_history_queue.empty():
                speed_history.append(speed_history_queue.get())

            speed_prediction = predict_speed(speed_history)
            if speed_prediction is not None and abs(speed_history[-1][0] * playback_multiplier - speed_prediction) < speed_prediction_minimum_difference:
                speed_prediction = speed_history[-1][0] * playback_multiplier

            time.sleep(0.1)
