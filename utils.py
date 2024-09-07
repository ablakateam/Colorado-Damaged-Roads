import os
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_coordinates_from_image(image_path):
    try:
        image = Image.open(image_path)
        exif = image._getexif()
        
        if not exif:
            return None
        
        gps_info = {}
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for key in value:
                    sub_tag = GPSTAGS.get(key, key)
                    gps_info[sub_tag] = value[key]
        
        if not gps_info:
            return None
        
        lat = gps_info.get('GPSLatitude')
        lat_ref = gps_info.get('GPSLatitudeRef')
        lon = gps_info.get('GPSLongitude')
        lon_ref = gps_info.get('GPSLongitudeRef')
        
        if not all([lat, lat_ref, lon, lon_ref]):
            return None
        
        lat = sum([float(x)/float(y) for x, y in lat])
        if lat_ref != 'N':
            lat = -lat
        
        lon = sum([float(x)/float(y) for x, y in lon])
        if lon_ref != 'E':
            lon = -lon
        
        return {'latitude': lat, 'longitude': lon}
    except Exception as e:
        print(f"Error extracting GPS data: {str(e)}")
        return None
