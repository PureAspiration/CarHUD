
def format_item(item: dict):
    item['id'] = item.pop("id", None)
    item['plz'] = item.pop("plz", None)
    item['state'] = item.pop("bundesland", None) or None
    item['district'] = item.pop("landkreis", None) or None
    item['location'] = item.pop("ort", None) or None
    item['suburb'] = item.pop("ortsteil", None) or None
    item['street'] = item.pop("strasse", None) or None
    item.pop("beschreibung", None)
    item['direction'] = item.pop("richtung", None)
    item['rotatable'] = bool(item.pop("drehbar", 0))
    item['create_time'] = item.pop("create_time", None)
    item['edit_time'] = item.pop("edit_time", None)
    item['country'] = item.pop("land", None)
    item.pop("laengengrad", None)
    item.pop("breitengrad", None)
    item.pop("gps_status", None)
    item.pop("beschreibung_short", None)
    item.pop("info1", None)
    item.pop("info2", None)
    item.pop("info3", None)
    item.pop("info4", None)
    item.pop("info5", None)
    item.pop("laengengrad_dezimal", None)
    item.pop("breitengrad_dezimal", None)
    item['lat'] = item.pop("lat", 0)
    item['lng'] = item.pop("lng", 0)
    cam_status = item.pop("status", None) or None
    cam_statuses = {
        "A": "Active",
        "L": "Empty",
        "Z": "Destroyed",
        None: "Unknown"
    }
    try:
        item['status'] = cam_statuses[cam_status]
    except KeyError:
        item['status'] = "Unknown"
    cam_type = item.pop("art", None) or None
    cam_speed = item.pop("vmax", "?") or "?"
    cam_types = {
        "G": "Speed camera",
        "A": "Red light camera",
        "GA": "Speed and traffic light enforcement",
        "SC": "Section control entry",
        "SCM": "Section control (Intermediate point)",
        "SCE": "Section control exit",
        "GK": "Weight control",
        "EK": "Passage control",
        "HK": "Height control",
        "BK": "Bus lane control",
        "UH": "No overtaking control",
        "UHV": "No overtaking control",
        "CP": "Stationary police spot check",
        "AK": "Distance control",
    }
    try:
        item['description'] = f"{cam_types[cam_type]}{f' {cam_speed} km/h' if cam_speed not in ['/', '?'] else ''}"
    except KeyError:
        item['description'] = None
        cam_code = item.pop('type', None)
        other_info = item['bubble'][item['bubble'].index('<strong>') + len('<strong>'):item['bubble'].index(' (ID')].strip()
        print(f"UNKNOWN TYPE CODE: {cam_code} or {cam_type}. There is also the following information: {other_info}")  # Get text between 2 substrings
    item.pop("type", None)
    item.pop("bubble", None)

    return item
