import exiftool
import pytest
import os
import datetime
import logging
from PIL import Image
import imagehash
import media_sifter

# custom class to be the mock return value
# will override the exiftool.ExifToolHelper returned from exiftool.ExifToolHelper()
class MockExiftoolHelper:
    # mock method always returns the data we pass in
    @staticmethod
    def get_metadata(test_data):
        # if we pass in the right file path, return the right data
        if test_data == "/my/path/media/folder3/file_exif.jpg":
            return [{
                "File:FileModifyDate": "2022:12:09 12:34:56",
                "File:FileName": "file_exif.jpg",
                "File:FileSize": "1",
                "File:FileType": "JPEG",
                "File:MIMEType": "image/jpeg",
                "File:Make": "Apple",
                "File:Model": "iPhone",
                "File:ModifyDate": "2022:12:09 12:34:56",
                "File:Orientation": "Horizontal (normal)",
                "File:Software": "13.2.1",
                "File:SubSecCreateDate": "2022:12:09 12:34:56.123",
                "File:SubSecDateTimeOriginal": "2022:12:09 12:34:56.123",
                "File:SubSecModifyDate": "2022:12:09 12:34:56.123",
                "File:XResolution": "72",
                "File:YCbCrPositioning": "Centered",
                "File:YResolution": "72",
                'EXIF:DateTimeOriginal': '2023:12:01 14:01:23',
                'EXIF:Model': 'Canon EOS-1D X Mark II',
                "Image:Aperture": "2.8",
                'EXIF:GPSLatitude': 1.0,
                'EXIF:GPSLatitudeRef': 'S',
                'EXIF:GPSLongitude': 2.0,
                'EXIF:GPSLongitudeRef': 'E',
                'EXIF:GPSAltitude': 3.0,
            }]
        return None
    
    def __init__(self):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        pass

@pytest.fixture
def cwd(fs, monkeypatch):
    fs.cwd = "/my/path"
    monkeypatch.setenv("HOME", "/home/user")

hasher = {}
def get_file_hash(path):
    if path not in hasher:
        return None
    return hasher[path]
def set_file_hash(path, hash):
    hasher[path] = hash

def create_nice_test_file(fs, name, hash, file_contents=None):
    if not file_contents:
        file_contents = "aaaa"
    fs.create_file(name, contents=file_contents)
    set_file_hash(name, hash)
    os.utime(name, times=(
        datetime.datetime(1972, 1, 1, 0, 0, 0, 0).timestamp(),
        datetime.datetime(1972, 1, 1, 0, 0, 0, 0).timestamp()
        ))

def create_example_filesystem(fs):
    # create a set of files and folders to test with
   # standard jpg
    create_nice_test_file(fs, "/my/path/media/folder1/normal.jpg", "1")
    # file with date in filename, and no hash
    create_nice_test_file(fs, "/my/path/media/folder2/file_20221209_1234.jpg", None)
    # file with exif data
    create_nice_test_file(fs, "/my/path/media/folder3/file_exif.jpg", "3")
    # file with json metadata
    create_nice_test_file(fs, "/my/path/media/folder3/file_json.jpg", "4")
    create_nice_test_file(fs, "/my/path/media/folder3/file_json.jpg.json", "4", file_contents="""{
  "title": "file_json.jpg",
  "description": "",
  "imageViews": "0",
  "creationTime": {
    "timestamp": "1705846415",
    "formatted": "21 Jan 2024, 14:13:35 UTC"
  },
  "photoTakenTime": {
    "timestamp": "1552477146",
    "formatted": "13 Mar 2019, 11:39:06 UTC"
  },
  "geoData": {
    "latitude": 18.553405599999998,
    "longitude": 73.9510639,
    "altitude": 560.6611940298508,
    "latitudeSpan": 0.0,
    "longitudeSpan": 0.0
  },
  "geoDataExif": {
    "latitude": 18.553405599999998,
    "longitude": 73.9510639,
    "altitude": 560.6611940298508,
    "latitudeSpan": 0.0,
    "longitudeSpan": 0.0
  },
  "url": "https://photos.google.com/photo/AF1QipN-OMtPqjnSG1_xEWY9DLvbJFqy3AEqrqlBNk1z",
  "googlePhotosOrigin": {
    "mobileUpload": {
      "deviceType": "IOS_PHONE"
    }
  }
}""")
    # file in a year folder
    create_nice_test_file(fs, "/my/path/media/folder 2014/file_year.jpg", "5")
    # file with date in the filename
    create_nice_test_file(fs, "/my/path/media/folder4/file_2018_02_01_101112_year.jpg", "6")
    # file with clashing hash in two different folders
    create_nice_test_file(fs, "/my/path/media/folder5/normal2.jpg", "1")
    # file with nothing but file modification time
    # movie file
    # RAW image file


def test_sift_media_empty(fs, cwd, caplog, monkeypatch):
    # test the media sifter with an empty subfolder
    fs.create_file("/my/path/media/nothing", contents=b"")
    ms = media_sifter.Media_Sifter("/my/path/media", "output", "report.json")
    ms.sift_media()
    # check we actually made a report
    assert os.path.isfile("/my/path/report.json")
    # read the results from the report file
    ms.read_report(backup=False)
    # check the report
    assert ms.report == {}

def test_sift_media_files(fs, cwd, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    # test the media sifter with a set of files
    create_example_filesystem(fs)
    # allow creation of mock hashes - mock PIL open to just return the filename and mock the
    # imagehash phash to use this filename to lookup the hash in our test dictionary
    def mock_pil_open(filename):
        return filename
    # apply the monkeypatch for PIL.open
    monkeypatch.setattr(Image, "open", mock_pil_open)
    def mock_imagehash_phash(image, hash_size):
        if image == 'error':
            raise OSError
        return get_file_hash(image)
    monkeypatch.setattr(imagehash, "phash", mock_imagehash_phash)
    monkeypatch.setattr(exiftool, "ExifToolHelper", MockExiftoolHelper)
    ms = media_sifter.Media_Sifter("/my/path/media", "output", "report.json")
    ms.sift_media()
    # check we actually made a report
    assert os.path.isfile("/my/path/report.json")
    # read the results from the report file
    ms.read_report(backup=False)
    expected_report = {
        '/my/path/media/folder1/normal.jpg': {
            'source': '/my/path/media/folder1/normal.jpg', 
            'folder_year': None, 
            'exif': {'datetime_exif': None, 'geodata_exif': None, 'model_exif': None}, 
            'file': {'datetime_filemodif': '1972-01-01 00:00:00', 'file_size': 4}, 
            'filename_time': {'datetime_filename': None}, 
            'hash': "1", 
            'json': {'datetime_json': None, 'geodata_json': None}, 
            'preferred_ts': '1972-01-01 00:00:00', 
            'destination': 'output/1972/1972_01/1972-01-01_000000_normal.jpg'
        }, 
        '/my/path/media/folder2/file_20221209_1234.jpg': {
            'source': '/my/path/media/folder2/file_20221209_1234.jpg', 
            'folder_year': None, 
            'exif': {'datetime_exif': None, 'geodata_exif': None, 'model_exif': None}, 
            'file': {'datetime_filemodif': '1972-01-01 00:00:00', 'file_size': 4}, 
            'filename_time': {'datetime_filename': '2022-12-09 12:34:00'}, 
            'hash': None, 
            'json': {'datetime_json': None, 'geodata_json': None}, 
            'preferred_ts': '2022-12-09 12:34:00', 
            'destination': 'output/2022/2022_12/2022-12-09_123400_file_20221209_1234.jpg'
        },
        '/my/path/media/folder3/file_exif.jpg': {
            'source': '/my/path/media/folder3/file_exif.jpg', 
            'folder_year': None, 
            'exif': {
                'datetime_exif': '2023-12-01 14:01:23', 
                'geodata_exif': {'latitude': -1.0, 'longitude': 2.0}, 
                'model_exif': 'Canon EOS-1D X Mark II'
            }, 
            'file': {'datetime_filemodif': '1972-01-01 00:00:00', 'file_size': 4}, 
            'filename_time': {'datetime_filename': None}, 
            'hash': "3", 
            'json': {'datetime_json': None, 'geodata_json': None}, 
            'preferred_ts': '2023-12-01 14:01:23', 
            'destination': 'output/2023/2023_12/2023-12-01_140123_file_exif.jpg'
        }, 
        '/my/path/media/folder3/file_json.jpg': {
            'source': '/my/path/media/folder3/file_json.jpg', 
            'folder_year': None, 
            'exif': {'datetime_exif': None, 'geodata_exif': None, 'model_exif': None}, 
            'file': {'datetime_filemodif': '1972-01-01 00:00:00', 'file_size': 4}, 
            'filename_time': {'datetime_filename': None}, 
            'hash': "4", 
            'json': {'datetime_json': '2019-03-13 11:39:06', 'geodata_json': {'latitude': 18.553405599999998, 'longitude': 73.9510639}}, 
            'preferred_ts': '2019-03-13 11:39:06', 
            'destination': 'output/2019/2019_03/2019-03-13_113906_file_json.jpg'
        },
        '/my/path/media/folder 2014/file_year.jpg': {  
            'source': '/my/path/media/folder 2014/file_year.jpg', 
            'folder_year': 2014, 
            'exif': {'datetime_exif': None, 'geodata_exif': None, 'model_exif': None}, 
            'file': {'datetime_filemodif': '1972-01-01 00:00:00', 'file_size': 4}, 
            'filename_time': {'datetime_filename': None}, 
            'hash': "5", 
            'json': {'datetime_json': None, 'geodata_json': None}, 
            'preferred_ts': '2014-01-01 00:00:00', 
            'destination': 'output/2014/2014_01/2014-01-01_000000_file_year.jpg'
        },
        '/my/path/media/folder4/file_2018_02_01_101112_year.jpg': {  
            'source': '/my/path/media/folder4/file_2018_02_01_101112_year.jpg', 
            'folder_year': None, 
            'exif': {'datetime_exif': None, 'geodata_exif': None, 'model_exif': None}, 
            'file': {'datetime_filemodif': '1972-01-01 00:00:00', 'file_size': 4}, 
            'filename_time': {'datetime_filename': '2018-02-01 10:11:12'}, 
            'hash': "6", 
            'json': {'datetime_json': None, 'geodata_json': None}, 
            'preferred_ts': '2018-02-01 10:11:12', 
            'destination': 'output/2018/2018_02/2018-02-01_101112_file_2018_02_01_101112_year.jpg'
        },
        '/my/path/media/folder5/normal2.jpg': {
            'source': '/my/path/media/folder5/normal2.jpg', 
            'folder_year': None, 
            'exif': {'datetime_exif': None, 'geodata_exif': None, 'model_exif': None}, 
            'file': {'datetime_filemodif': '1972-01-01 00:00:00', 'file_size': 4}, 
            'filename_time': {'datetime_filename': None}, 
            'hash': "1", 
            'json': {'datetime_json': None, 'geodata_json': None}, 
            'preferred_ts': '1972-01-01 00:00:00', 
            'destination': 'output/1972/1972_01/1972-01-01_000000_normal2.jpg'
        }        
    }
    # check the report
    assert ms.report == expected_report

    # If we run a second time it should read the report and not do anything
    ms.sift_media()
    # read the results from the report file
    ms.read_report(backup=False)
    # check the report
    assert ms.report == expected_report

    # create a zero sized image to give exiftool a surprise
    #fs.create_file("/my/path/zero.jpg", contents=b"")
    #os.utime("/my/path/zero.jpg", times=(
    #    datetime.datetime(1972, 1, 1, 0, 0, 0, 0).timestamp(),
    #    datetime.datetime(1972, 1, 1, 0, 0, 0, 0).timestamp()
    #    ))
    # apply the monkeypatch for exiftool
    #monkeypatch.setattr(exiftool, "ExifToolHelper", MockExiftoolHelper)
