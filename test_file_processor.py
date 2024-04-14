from typing import Any
from file_processor import *
import exiftool
import pytest

def test_find_date():
    assert find_date("2020-01-01") == datetime.datetime(2020,1,1,0,0)  
    assert find_date("bobbins20120901_114223_edited.jpg") == datetime.datetime(2012, 9, 1, 11, 42, 23)
    assert find_date("bobbins20120901_114223.jpg") == datetime.datetime(2012, 9, 1, 11, 42, 23)
    assert find_date("2100_01_01") == None

def test_is_exif():
    assert is_exif(".spoon") == False
    assert is_exif(".JSON") == False
    all_media = ext_video + ext_image_PIL + ext_non_PIL
    assert all([is_exif(x) for x in all_media]) == True
    assert all([is_exif(x.upper()) for x in all_media]) == True

def test_is_video():
    assert is_video(".spoon") == False
    assert is_video(".JSON") == False
    assert all([is_video(x) for x in ext_video]) == True
    assert all([is_video(x.upper()) for x in ext_video]) == True    
    assert all([is_video(x) for x in ext_non_PIL]) == False

def test_is_image():
    assert is_image(".spoon") == False
    assert is_image(".JSON") == False
    images = ext_image_PIL + ext_non_PIL
    assert all([is_image(x) for x in images]) == True
    assert all([is_image(x.upper()) for x in images]) == True

def test_file_processor_exif_gps_helper():
    mapper = {}
    year = 2024
    outfolder = "test"

    fp = File_Processor(mapper, year, outfolder)
    exif1 = {
        'EXIF:GPSLatitude': 1.0,
        'EXIF:GPSLatitudeRef': 'N',
        'EXIF:GPSLongitude': 2.0,
        'EXIF:GPSLongitudeRef': 'E',
        'EXIF:GPSAltitude': 3.0,
    }
    assert fp.exif_gps_helper(exif1) == {
        'latitude': 1.0,
        'longitude': 2.0,
    }
    exif2 = {
        'EXIF:GPSLatitude': 1.0,
        'EXIF:GPSLatitudeRef': 'S',
        'EXIF:GPSLongitude': 2.0,
        'EXIF:GPSLongitudeRef': 'E',
        'EXIF:GPSAltitude': 3.0,
    }
    assert fp.exif_gps_helper(exif2) == {
        'latitude': -1.0,
        'longitude': 2.0,
    }
    exif3 = {
        'EXIF:GPSLatitude': 1.0,
        'EXIF:GPSLatitudeRef': 'N',
        'EXIF:GPSLongitude': 2.0,
        'EXIF:GPSLongitudeRef': 'W',
        'EXIF:GPSAltitude': 3.0,
    }
    assert fp.exif_gps_helper(exif3) == {
        'latitude': 1.0,
        'longitude': -2.0,
    }
    exif4 = {
        'EXIF:GPSLatitude': 1.0,
        'EXIF:GPSLongitude': 2.0,
        'EXIF:GPSAltitude': 3.0,
    }
    assert fp.exif_gps_helper(exif4) == {
        'latitude': 1.0,
        'longitude': 2.0,
    }

# custom class to be the mock return value
# will override the exiftool.ExifToolHelper returned from exiftool.ExifToolHelper()
class MockExiftoolHelper:
    # mock method always returns a specific testing dictionary
    @staticmethod
    def get_metadata(test_data):
        return test_data
    
    def __init__(self):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        pass

def test_file_processor_get_exif_metadata(monkeypatch):
    mapper = {}
    year = 2024
    outfolder = "test"

    # apply the monkeypatch for exiftool
    monkeypatch.setattr(exiftool, "ExifToolHelper", MockExiftoolHelper)

    fp = File_Processor(mapper, year, outfolder)
    test = [{
        'EXIF:DateTimeOriginal': '2023:12:01 14:01:23',
        'EXIF:Model': 'Canon EOS-1D X Mark II',
        'EXIF:GPSLatitude': 1.0,
        'EXIF:GPSLongitude': 2.0,
        'EXIF:GPSAltitude': 3.0,
    }]
    fp.source_media_filename = test
    md = fp.get_exif_metadata() 
    assert md == {
        'datetime_exif': datetime.datetime(2023,12,1,14,1,23,0),
        'model_exif': 'Canon EOS-1D X Mark II',
        'geodata_exif': {
            'latitude': 1.0,
            'longitude': 2.0,
        }
    }
    test2 = [{
        'QuickTime:CreateDate': '2023:12:01 14:01:23',
        'EXIF:Model': 'Canon EOS-1D X Mark II',
        'EXIF:GPSLatitude': 1.0,
        'EXIF:GPSLongitude': 2.0,
        'EXIF:GPSAltitude': 3.0,
    }]
    fp.source_media_filename = test2
    md = fp.get_exif_metadata() 
    assert md == {
        'datetime_exif': datetime.datetime(2023,12,1,14,1,23,0),
        'model_exif': 'Canon EOS-1D X Mark II',
        'geodata_exif': {
            'latitude': 1.0,
            'longitude': 2.0,
        }
    }

def test_get_filename_metadata():
    mapper = {}
    year = 2024
    outfolder = "test"

    fp = File_Processor(mapper, year, outfolder)
    fp.source_media_basename = "bobbins20120901_114223_edited.jpg"
    md = fp.get_filename_metadata()
    assert md == {
        'datetime_filename': datetime.datetime(2012, 9, 1, 11, 42, 23, 0),
    } 

def test_file_metadata(monkeypatch):
    mapper = {}
    year = 2024
    outfolder = "test"

    # mock the os.path.getmtime method to return whatever data is passed in
    def mock_getmtime(filename):
        return filename
    
    # apply the monkeypatch for os.path.getmtime
    monkeypatch.setattr(os.path, "getmtime", mock_getmtime)

    fp = File_Processor(mapper, year, outfolder)
    fp.source_media_filename = datetime.datetime(2023, 12, 1, 14, 1, 23, 0).timestamp()
    md = fp.get_file_metadata()
    assert md == {
        'datetime_filemodif': datetime.datetime(2023, 12, 1, 14, 1, 23, 0),
    }

def test_json_metadata():
    mapper = {}
    year = 2024
    outfolder = "test"

    fp = File_Processor(mapper, year, outfolder)
    fp.json_mapper = {}
    fp.source_media_filename = "sponge/bobbins20120901_114223_edited.jpg"
    fp.source_media_basename = "bobbins20120901_114223_edited.jpg"
    md = fp.get_json_metadata()
    assert md == {
        'datetime_json': None,
        'geodata_json': None
    }