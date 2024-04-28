from PIL import Image
import imagehash
import exiftool
import logging
import json
import datetime
import os
import re
import magic

ext_video = ['.3gp', '.avi', '.mov', '.m4v', '.mp4']
ext_image_PIL = ['.jpg', '.jpeg', '.heic', '.bmp', '.tif', '.tiff', '.png', '.gif']
ext_non_PIL = ['.nef', '.dng', '.psd', '.pef']
ext_json = ['.json']

def find_date(instr):
    # Try and find an ISO format (roughly) date in a filename. Python's datefinder module wasn't very successful at doing this
    # so I had to craft my own.
    # try YYYY-MM-DD-HH-MM-SS
    try:
        m = re.match(r'.*(20[012]\d).?([01]\d).?([0-3]\d).?([012]\d).?([0-5]\d).?([0-5]\d).*', instr)
        if m:
            dt = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), 0)
            return dt
        # try YYYY-MM-DD-HH-MM
        m = re.match(r'.*(20[012]\d).?([01]\d).?([0-3]\d).?([012]\d).?([0-5]\d).*', instr)
        if m:
            dt = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), 0, 0)
            return dt
        # try YYYY-MM-DD
        m = re.match(r'.*(20[012]\d).?([01]\d).?([0-3]\d).*', instr)
        if m:
            dt = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 0, 0, 0, 0)
            return dt
    except ValueError:
        logging.warning("find_date - Error converting value in %s to a date", instr)
    return None

def is_exif(ext):
    return is_image(ext) or is_video(ext)

def is_video(ext):
    return ext.lower() in ext_video

def is_image(ext):
    return is_image_PIL(ext) or is_non_PIL(ext)

def is_image_PIL(ext):
    return ext.lower() in ext_image_PIL

def is_non_PIL(ext):
    return ext.lower() in ext_non_PIL

def is_json(ext):
    return ext.lower() in ext_json

class File_Processor:
    '''
        Class which processes individual media files, extracts metadata from a number of sources
        and suggests a new output filename in which to store the media. Uses sidecar json files 
        if avilable, exif data and timestamps embedded in the filename itself e.g. by certain
        makes of phones and cameras.
        Produces a hashmap of results for each file processed which can be later used to rename
        and update the metadata in the file itself.
    '''
    def __init__(self, json_mapper, year, outfolder):
        self.json_mapper = json_mapper
        self.year_hint = year
        self.output_folder = outfolder

    def exif_gps_helper(self, d):
        '''
            Helper function to extract GPS data from exif data.
        '''
        result = {
            'latitude': None,
            'longitude': None
        }
        if 'EXIF:GPSLatitude' in d:
            if 'EXIF:GPSLatitudeRef' in d:
                result['latitude'] = d['EXIF:GPSLatitude'] if d['EXIF:GPSLatitudeRef']=='N' else -1 * d['EXIF:GPSLatitude']
            else:
                result['latitude'] = d['EXIF:GPSLatitude']
        if 'EXIF:GPSLongitude' in d:
            if 'EXIF:GPSLongitudeRef' in d:
                result['longitude'] = d['EXIF:GPSLongitude'] if d['EXIF:GPSLongitudeRef']=='E' else -1 * d['EXIF:GPSLongitude']
            else:
                result['longitude'] = d['EXIF:GPSLongitude']
        return result
        
    def get_exif_metadata(self):
        metadata_exif = {
            'datetime_exif': None,
            'geodata_exif': None,
            'model_exif': None
        }
        # Look for exif data already existing
        try:
            with exiftool.ExifToolHelper() as et:
                metadata = et.get_metadata(self.source_media_filename)
                logging.debug("File_Processor : get_exif_metadata - %s", metadata)
                for d in metadata:
                    if 'EXIF:DateTimeOriginal' in d:
                        metadata_exif['datetime_exif'] = find_date(d['EXIF:DateTimeOriginal'])                    
                    elif 'QuickTime:CreateDate' in d:
                        metadata_exif['datetime_exif'] = find_date(d['QuickTime:CreateDate'])
                    metadata_exif['geodata_exif'] = self.exif_gps_helper(d)
                    if 'EXIF:Model' in d:
                        metadata_exif['model_exif'] = d['EXIF:Model']
        except exiftool.exceptions.ExifToolExecuteError as e:
            logging.error("File_Processor : get_exif_metadata - Error reading exif data for %s - %s",
                          self.source_media_filename, e)
        return metadata_exif

    def get_filename_metadata(self):
        # Look for datetime in filename itself
        return {
            'datetime_filename': find_date(self.source_media_basename),
        }

    def get_file_metadata(self):
        # read modification timestamp from candidate
        return {
            'datetime_filemodif': datetime.datetime.fromtimestamp(os.path.getmtime(self.source_media_filename)),
            'file_size': os.path.getsize(self.source_media_filename)
        }

    def read_json_file(self, json_filename):
        with open(json_filename) as f:
            d = json.load(f)
        return d
    
    def get_json_metadata(self):
        # Look for a matching json file
        metadata_json = {
            'datetime_json': None,
            'geodata_json': None
        }
        if self.source_media_basename in self.json_mapper:
            json_filename = os.path.dirname(self.source_media_filename)+"/"+self.json_mapper[self.source_media_basename]
            d = self.read_json_file(json_filename)
            # do some sense checks on the json data
            if 'photoTakenTime' in d:
                datetime_ts_json = d['photoTakenTime']['timestamp']
                metadata_json['datetime_json'] = datetime.datetime.fromtimestamp(int(datetime_ts_json))
            else:
                logging.warning("File_Processor : get_json_metadata - No photoTakenTime in %s", json_filename)
            if 'geoData' in d:
                metadata_json['geodata_json'] = {
                    'latitude': d['geoData']['latitude'],
                    'longitude': d['geoData']['longitude'],
                }
            else:
                logging.warning("File_Processor : get_json_metadata - No geoData in %s", json_filename)
        else:
            logging.debug("File_Processor : get_json_metadata - No json file for %s", self.source_media_filename)
        return metadata_json    
    
    def get_hash(self):
        if is_image_PIL(self.source_media_fileext):
            return self.get_image_hash()
        elif is_video(self.source_media_fileext):
            return None
            #return self.get_video_hash() # seems to get a lot of collisions
        else:
            return None

    #def get_video_hash(self):
    #    return videohash.VideoHash(path=self.source_media_filename).hash_hex

    def get_image_hash(self):        
        # Experimenting with different hash sizes and types. Average hash produced a lot of 
        # collisions with similar but different pictures - e.g. one taken immediately after
        # another. Perceptual hash worked better, but bumping hash size up from 8 to try 
        # and reduce collisions further.
        try:
            hash = imagehash.phash(Image.open(self.source_media_filename), hash_size=16)
            return hash
        except OSError as e:
            logging.error("File_Processor : get_image_hash - %s from %s", e, self.source_media_filename)
            return None
    
    def process_file(self, source):
        self.source_media_filename = source
        self.source_media_basename = os.path.basename(source)
        cfile, self.source_media_fileext = os.path.splitext(self.source_media_filename)
        if is_exif(self.source_media_fileext):
            results = {
                'source': self.source_media_filename,
                'folder_year': self.year_hint,
                'exif': self.get_exif_metadata(),
                'file': self.get_file_metadata(),
                'filename_time': self.get_filename_metadata(),
                'hash': self.get_hash(),
                'json': self.get_json_metadata()
            }
            # if the file size is zero, log an error
            if results['file']['file_size'] == 0:
                logging.error("File_Processor : process_file - Zero size file %s", self.source_media_filename)
            # if we're in a folder that contains a year, use this as a bad fallback time for the media
            if self.year_hint:
                year_hint_time = datetime.datetime(self.year_hint, 1, 1, 0, 0, 0, 0)
            else:
                year_hint_time = None
            # choose a timestamp for the photo using these methods in preference order
            results['preferred_ts'] = (
                results['exif']['datetime_exif'] or 
                results['json']['datetime_json'] or
                results['filename_time']['datetime_filename'] or
                year_hint_time or
                results['file']['datetime_filemodif']
            )
            logging.debug("File_Processor : process_file - results: %s preferred_ts %s", results, results['preferred_ts'])
            # come up with a proposed new name for the file
            destination = "{0}/{1:%Y}/{1:%Y}_{1:%m}/{1:%Y-%m-%d_%H%M%S}_{2}".format(self.output_folder, results['preferred_ts'], self.source_media_basename)
            results['destination'] = destination
            return results
        elif is_json(self.source_media_fileext):
            pass
        else:
            ftype = magic.from_file(self.source_media_filename, mime=True)
            logging.error("File_Processor : process_file - Found an extension I don't like: %s %s (mime type is %s)", self.source_media_filename, self.source_media_fileext, ftype)
        return None
