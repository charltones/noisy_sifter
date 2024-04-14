from typing import Any
from file_processor import *
import exiftool
from PIL import Image
import imagehash
import magic
import pytest

def test_find_date():
    assert find_date("2020-01-01") == datetime.datetime(2020,1,1,0,0)  
    assert find_date("bobbins20120901_114223_edited.jpg") == datetime.datetime(2012, 9, 1, 11, 42, 23)
    assert find_date("bobbins20120901_114223.jpg") == datetime.datetime(2012, 9, 1, 11, 42, 23)
    assert find_date("bobbins20120901_1142.jpg") == datetime.datetime(2012, 9, 1, 11, 42, 0)
    assert find_date("2000_01_32") == None
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

def test_read_json_file(mocker):
    mocked_json_data = mocker.mock_open(read_data="{\"spud\":\"nice\"}")
    builtin_open = "builtins.open"
    mocker.patch(builtin_open, mocked_json_data)

    mapper = {}
    year = 2024
    outfolder = "test"
    fp = File_Processor(mapper, year, outfolder)
    assert fp.read_json_file("test.json") == {'spud':'nice'}

# custom class to be the mock return value
# will override the exiftool.ExifToolHelper returned from exiftool.ExifToolHelper()
class MockExiftoolHelper:
    # mock method always returns the data we pass in
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

def test_json_metadata(monkeypatch):
    mapper = {}
    year = 2024
    outfolder = "test"

    # Test that when json mapper is empty we get the empty metadata back
    fp = File_Processor(mapper, year, outfolder)
    fp.json_mapper = {}
    fp.source_media_filename = "sponge/bobbins20120901_114223_edited.jpg"
    fp.source_media_basename = "bobbins20120901_114223_edited.jpg"
    md = fp.get_json_metadata()
    assert md == {
        'datetime_json': None,
        'geodata_json': None
    }

    def mock_read_json_file(self, filename):
        assert filename == "sponge/bobbins20120901_114223_edited.jpg.json"
        return {
            'photoTakenTime': {
                'timestamp': datetime.datetime(2023, 12, 1, 14, 1, 23, 0).timestamp()
            },
            'geoData': {
                'latitude': 1.0,
                'longitude': 2.0,
            }
        }
          
    # test that when there is a matching json mapper we get the correct metadata back
    File_Processor.read_json_file = mock_read_json_file
    fp = File_Processor(mapper, year, outfolder)
    fp.source_media_filename = "sponge/bobbins20120901_114223_edited.jpg"
    fp.source_media_basename = "bobbins20120901_114223_edited.jpg"
    fp.json_mapper = {
        fp.source_media_basename: fp.source_media_basename+".json"
    }
    md = fp.get_json_metadata()
    assert md == {
        'datetime_json': datetime.datetime(2023, 12, 1, 14, 1, 23, 0),
        'geodata_json': {
                'latitude': 1.0,
                'longitude': 2.0,
        }
    }

    def mock_read_json_file2(self, filename):
        assert filename == "sponge/bobbins20120901_114223_edited.jpg.json"
        return {
            'photoTakenTime': {
                'timestamp': datetime.datetime(2023, 12, 1, 14, 1, 23, 0).timestamp()
            },
        }
          
    # test that when there is a matching json mapper we get the correct metadata back
    File_Processor.read_json_file = mock_read_json_file2
    fp = File_Processor(mapper, year, outfolder)
    fp.source_media_filename = "sponge/bobbins20120901_114223_edited.jpg"
    fp.source_media_basename = "bobbins20120901_114223_edited.jpg"
    fp.json_mapper = {
        fp.source_media_basename: fp.source_media_basename+".json"
    }
    md = fp.get_json_metadata()
    assert md == {
        'datetime_json': datetime.datetime(2023, 12, 1, 14, 1, 23, 0),
        'geodata_json': None
    }

    def mock_read_json_file3(self, filename):
        assert filename == "sponge/bobbins20120901_114223_edited.jpg.json"
        return {
            'geoData': {
                'latitude': 1.0,
                'longitude': 2.0,
            }
        }
          
    # test that when there is a matching json mapper we get the correct metadata back
    File_Processor.read_json_file = mock_read_json_file3
    fp = File_Processor(mapper, year, outfolder)
    fp.source_media_filename = "sponge/bobbins20120901_114223_edited.jpg"
    fp.source_media_basename = "bobbins20120901_114223_edited.jpg"
    fp.json_mapper = {
        fp.source_media_basename: fp.source_media_basename+".json"
    }
    md = fp.get_json_metadata()
    assert md == {
        'datetime_json': None,
        'geodata_json': {
                'latitude': 1.0,
                'longitude': 2.0,
        }
    }

def test_get_hash(monkeypatch):
    mapper = {}
    year = 2024
    outfolder = "test"

    def mock_pil_open(filename):
        return filename
    # apply the monkeypatch for PIL.open
    monkeypatch.setattr(Image, "open", mock_pil_open)

    def mock_imagehash_phash(image, hash_size):
        if image == 'error':
            raise OSError
        return "hash"
    monkeypatch.setattr(imagehash, "phash", mock_imagehash_phash)
  
    # Test that when we ask for an image hash of unsupported we get None
    fp = File_Processor(mapper, year, outfolder)
    fp.source_media_fileext = ".blob"
    fp.source_media_filename = "sponge/bobbins20120901_114223_edited.blob"
    assert fp.get_hash() == None

    # Test that when we ask for an image hash of video we get None
    fp = File_Processor(mapper, year, outfolder)
    fp.source_media_fileext = ".avi"
    fp.source_media_filename = "sponge/bobbins20120901_114223_edited.avi"
    assert fp.get_hash() == None

    # Test that when we ask for an image hash of image that causes error we get None
    fp = File_Processor(mapper, year, outfolder)
    fp.source_media_fileext = ".jpg"
    fp.source_media_filename = "error"
    assert fp.get_hash() == None

    # Test that when we ask for an image hash of image we get the right hash
    fp = File_Processor(mapper, year, outfolder)
    fp.source_media_fileext = ".jpg"
    fp.source_media_filename = "sponge/bobbins20120901_114223_edited.jpg"
    assert fp.get_hash() == "hash"
  
def test_process_file(monkeypatch):
    # test skipping json file
    mapper = {}
    year = 2024
    outfolder = "test"
    fp = File_Processor(mapper, year, outfolder)
    assert fp.process_file("folder/basename.json") == None

    # test skipping unknown file
    def mock_magic_from_file(filename, mime):
        assert filename == "folder/basename"
        return filename
    monkeypatch.setattr(magic, "from_file", mock_magic_from_file)
    assert fp.process_file("folder/basename") == None

    # test processing a regular media file
    def mock_get_exif_metadata(self):
        if self.source_media_filename == "folder/test1.jpg":
            return {
                'datetime_exif': datetime.datetime(2023,12,1,14,1,23,0),
            }
        else:
            return {
                'datetime_exif': None
            }
    def mock_get_file_metadata(self):
        if self.source_media_filename == "folder/test5.jpg":
            return {
                'datetime_filemodif': datetime.datetime(2023,12,5,14,1,23,0),
            }
        else:
            return {
                'datetime_filemodif': None,
            }
    def mock_get_filename_metadata(self):
        if self.source_media_filename == "folder/test3.jpg":
            return {
                'datetime_filename': datetime.datetime(2023,12,3,14,1,23,0),
            }
        else:
            return {
                'datetime_filename': None,
            }
    def mock_get_hash(self):
       return 'hash'
    def mock_get_json_metadata(self):
        if self.source_media_filename == "folder/test2.jpg":
            return {
                'datetime_json': datetime.datetime(2023,12,2,14,1,23,0),
            }
        else:
            return {
                'datetime_json': None,
            }
    File_Processor.get_exif_metadata = mock_get_exif_metadata
    File_Processor.get_file_metadata = mock_get_file_metadata
    File_Processor.get_filename_metadata = mock_get_filename_metadata
    File_Processor.get_hash = mock_get_hash
    File_Processor.get_json_metadata = mock_get_json_metadata
    fp = File_Processor(mapper, year, outfolder)
    # test 1 - exif data present
    assert fp.process_file("folder/test1.jpg") == {
        'source': "folder/test1.jpg",
        'folder_year': 2024,
        'exif': {
                'datetime_exif': datetime.datetime(2023,12,1,14,1,23,0),
            },
        'file_time': {
                'datetime_filemodif': None,
            },
        'filename_time': {
                'datetime_filename': None,
            },
        'hash': 'hash',
        'json': {
                'datetime_json': None,
            },
        'preferred_ts': datetime.datetime(2023,12,1,14,1,23,0),
        'destination': 'test/2023/2023_12/2023-12-01_140123_test1.jpg'
    }

    # test 2 - json data present
    assert fp.process_file("folder/test2.jpg") == {
        'source': "folder/test2.jpg",
        'folder_year': 2024,
        'exif': {
                'datetime_exif': None,
            },
        'file_time': {
                'datetime_filemodif': None,
            },
        'filename_time': {
                'datetime_filename': None,
            },
        'hash': 'hash',
        'json': {
                'datetime_json': datetime.datetime(2023,12,2,14,1,23,0),
            },
        'preferred_ts': datetime.datetime(2023,12,2,14,1,23,0),
        'destination': 'test/2023/2023_12/2023-12-02_140123_test2.jpg'
    }

    # test 3 - filename data present
    assert fp.process_file("folder/test3.jpg") == {
        'source': "folder/test3.jpg",
        'folder_year': 2024,
        'exif': {
                'datetime_exif': None,
            },
        'file_time': {
                'datetime_filemodif': None,
            },
        'filename_time': {
                'datetime_filename': datetime.datetime(2023,12,3,14,1,23,0),
            },
        'hash': 'hash',
        'json': {
                'datetime_json': None,
            },
        'preferred_ts': datetime.datetime(2023,12,3,14,1,23,0),
        'destination': 'test/2023/2023_12/2023-12-03_140123_test3.jpg'
    }

    # test 4 - year hint present
    assert fp.process_file("folder/test4.jpg") == {
        'source': "folder/test4.jpg",
        'folder_year': 2024,
        'exif': {
                'datetime_exif': None,
            },
        'file_time': {
                'datetime_filemodif': None,
            },
        'filename_time': {
                'datetime_filename': None,
            },
        'hash': 'hash',
        'json': {
                'datetime_json': None,
            },
        'preferred_ts': datetime.datetime(2024,1,1,0,0,0,0),
        'destination': 'test/2024/2024_01/2024-01-01_000000_test4.jpg'
    }

    # test 5 - file modif present
    fp = File_Processor(mapper, None, outfolder)
    assert fp.process_file("folder/test5.jpg") == {
        'source': "folder/test5.jpg",
        'folder_year': None,
        'exif': {
                'datetime_exif': None,
            },
        'file_time': {
                'datetime_filemodif': datetime.datetime(2023,12,5,14,1,23,0),
            },
        'filename_time': {
                'datetime_filename': None,
            },
        'hash': 'hash',
        'json': {
                'datetime_json': None,
            },
        'preferred_ts': datetime.datetime(2023,12,5,14,1,23,0),
        'destination': 'test/2023/2023_12/2023-12-05_140123_test5.jpg'
    }


