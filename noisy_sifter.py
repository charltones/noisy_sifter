#!/usr/bin/python3

import exiftool
import argparse
import glob, os, re
import magic
import json
import datetime
import sys
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', filename='noisy_sifter.log', level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler())
            
ext_exif = ['.jpg', '.jpeg', '.heic', '.3gp', '.avi', '.bmp', '.tif', '.tiff', '.pef', '.mov', '.m4v', '.png', '.gif',
             '.mp4', '.nef', '.dng', '.psd']
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
    return ext.lower() in ext_exif

def is_json(ext):
    return ext in ext_json

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
        datetime_exif = None
        datetimestring_exif = None
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
        }

    def get_json_metadata(self):
        # Look for a matching json file
        metadata_json = {
            'datetime_json': None,
            'geodata_json': None
        }
        if self.source_media_basename in self.json_mapper:
            json_filename = os.path.dirname(self.source_media_filename)+"/"+self.json_mapper[self.source_media_basename]
            with open(json_filename) as f:
                d = json.load(f)
            # do some sense checks on the json data
            if 'photoTakenTime' in d:
                datetime_ts_json = d['photoTakenTime']['timestamp']
                metadata_json['datetime_json'] = datetime.datetime.fromtimestamp(int(datetime_ts_json))
            else:
                logger.warning("File_Processor : get_json_metadata - No photoTakenTime in %s", json_filename)
            if 'geoData' in d:
                metadata_json['geodata_json'] = {
                    'latitude': d['geoData']['latitude'],
                    'longitude': d['geoData']['longitude'],
                }
            else:
                logger.warning("File_Processor : get_json_metadata - No geoData in %s", json_filename)
        else:
            logger.warning("File_Processor : get_json_metadata - No json file for %s", self.source_media_filename)
        return metadata_json    

    def process_file(self, source):
        self.source_media_filename = source
        self.source_media_basename = os.path.basename(source)
        cfile, self.source_media_fileext = os.path.splitext(self.source_media_filename)
        if is_exif(self.source_media_fileext):
            results = {
                'source': self.source_media_filename,
                'folder_year': self.year_hint,
                'exif': self.get_exif_metadata(),
                'file_time': self.get_file_metadata(),
                'filename_time': self.get_filename_metadata(),
                'json': self.get_json_metadata()
            }
            # if we're in a folder that contains a year, use this as a bad fallback time for the media
            if self.year_hint:
                year_hint_time = datetime.datetime(self.year_hint, 1, 1, 0, 0, 0, 0)
            else:
                year_hint_time = None
            # choose a timestamp for the photo using these methods in preference order
            preferred_ts = (
                results['exif']['datetime_exif'] or 
                results['json']['datetime_json'] or
                results['filename_time']['datetime_filename'] or
                year_hint_time or
                results['file_time']['datetime_filemodif']
            )
            logging.debug("File_Processor : process_file - results: %s preferred_ts %s", results, preferred_ts)
            # come up with a proposed new name for the file
            destination = "{0}/{1:%Y}/{1:%Y}_{1:%m}/{1:%Y-%m-%d_%H%M%S}_{2}".format(self.output_folder, preferred_ts, self.source_media_basename)
            results['destination'] = destination
            return results
        elif is_json(self.source_media_fileext):
            pass
        else:
            ftype = magic.from_file(self.source_media_filename, mime=True)
            logging.error("File_Processor : process_file - Found an extension I don't like: %s %s (mime type is %s)", self.source_media_filename, self.source_media_fileext, ftype)
        return None

class JSON_Mapper:
    '''
        Class which processes a folder of media files which also may contain json sidecar files. It 
        attempts to map the media files to the corresponding json files. This process is complex
        due to the generally buggy way that Google has implemented Takeout for photos.
    '''
    def __init__(self, input_folder):
        self.input_folder = input_folder
        self.mapper = {}

    def create_mapper(self):
        # find all json files in the specified input folder
        # open the file and read the details into a hashmap
        # try to identify the mapping from json file to target media file
        # needs some cleverness to work out when multiple files have same name!
        for json_filename in glob.iglob(self.input_folder + "//*.json", recursive=False):
            self.json_filename = json_filename
            self.json_basename = os.path.basename(json_filename)
            self.json_basename_noext, self.json_fileext = os.path.splitext(self.json_basename)
             # We're not interested in metadata*.json
            if re.match(r"metadata.*", self.json_basename):
                pass
            else:
                self.process_json()
        return self.mapper

    def process_target_media_filename(self):
        self.target_media_filename = self.json_document['title']
        self.target_media_filename_noext, self.target_media_fileext = os.path.splitext(self.target_media_filename)

        if len(self.target_media_filename) > 46:
            self.over_46_chars_media_filename = True
            self.add_file_extension = True
        else:
            self.over_46_chars_media_filename = False
            if len(self.target_media_fileext)==0:
                # Google what the actual?
                # Sometimes the json file target filename has no extension, but the media file is a jpg?!
                self.target_media_fileext = '.jpg'
                self.add_file_extension = True
            else:
                self.add_file_extension = False
        # replace ' in title with _ and truncate to 46 characters
        # why? You'll need to ask Google
        self.target_media_filename_truncated = self.target_media_filename.replace('\'', '_')[:46]

    def process_json_basename_match(self):
        # most of the time the image file for image.ext is image.ext.json

        # if our 46 character truncation chops the middle of our file extension, then remove it
        m = re.match(r"^(.*)\..?.?$", self.target_media_filename_truncated)
        if m:
            self.target_media_filename_truncated = m.group(1)
        
        # if our media file is missing a file extension, add it back on
        if self.add_file_extension:
            self.target_media_filename_truncated += self.target_media_fileext
        
        for check in ['normal', '47chars']:
            # check that the media file actually exists
            if os.path.isfile(self.input_folder+'/'+self.target_media_filename_truncated):
                # save the media file in the mapper - this is the happy path complete
                logging.debug("JSON_Mapper : process_jason_basename_match - found file %s -> %s", self.target_media_filename_truncated, self.json_basename)
                self.mapper[self.target_media_filename_truncated] = self.json_basename
                if check=='47chars':
                    logging.warning("JSON_Mapper : process_jason_basename_match - found file with 47 chars trick %s", self.target_media_filename_truncated)
                break
            else:
                # If the first file exists check fails, try media file but truncated to
                # 47 characters instead of 46!
                if self.over_46_chars_media_filename:
                    self.target_media_filename_truncated =  self.target_media_filename.replace('\'', '_')[:47]+self.target_media_fileext

        if self.target_media_filename_truncated not in self.mapper:
            # we failed to make a match - log an error
            logging.error("JSON_Mapper : process_jason_basename_match - media file not found %s", self.target_media_filename_truncated)

    def process_json_basename_mismatch(self):
        # The media filename in the json file doesn't match the json document
        # The normal reason for this is that the media file and json document have been 
        # renamed with a numbered index.

        # Match a numbered index on the json file
        m = re.match(r"(.*)\.\w{1,4}\(\d+\)$", self.json_basename_noext)
        if m:
            # we now need to match up the numbered files to resolve ambiguities - we do this slightly
            # inefficiently by always processing all of the numbered indexes whenever we find a single one
            # so we're overprocessing the files, but the only sane way of doing this is to start from zero
            # and count up so we're just going to have to live with that.
            base_numbering_file = m.group(1)
            # the target media file doesn't have truncated file extensions in it, but the json does!
            m = re.match(r"^(.*)\.\w{1,2}$", self.target_media_filename_truncated)
            if m:
                self.target_media_filename_truncated = m.group(1)
            if self.add_file_extension:
                self.target_media_filename_truncated += self.target_media_fileext

            if base_numbering_file+self.target_media_fileext==self.target_media_filename_truncated:
                joffset = 0
                # check all the numbered json files and media files line up correctly
                for index in range(20):
                    if index==0:
                        checkm = base_numbering_file+self.target_media_fileext
                        checkj = base_numbering_file+self.target_media_fileext+self.json_fileext
                    else:
                        checkm = "{}({}){}".format(base_numbering_file,index,self.target_media_fileext)
                        checkj = "{}{}({}){}".format(base_numbering_file,self.target_media_fileext,index+joffset,self.json_fileext)
                    media_exists = os.path.isfile(self.input_folder+'/'+checkm)
                    json_exists = os.path.isfile(self.input_folder+'/'+checkj)
                    if media_exists and json_exists:
                        checkj2 = "{}({}){}{}".format(base_numbering_file,index,self.target_media_fileext,self.json_fileext)
                        json2_exists = os.path.isfile(self.input_folder+'/'+checkj2)
                        if json2_exists:
                            # if there was actually a media file uploaded called image(1).ext and google wants to write a second
                            # image(1).ext, then it will have the first as image(1).ext -> image(1).ext.json (note position of
                            # number) and then write out the second as image(2).ext -> image.ext(1).json
                            # Because of this corner case, we need to record a json file index offset, as the media file and
                            # json file index will get out of sync after this. We also don't want to cross match the wrong
                            # media and json files, so we don't record this 'match' and skip to the next index
                            joffset -= 1
                            logging.warning("JSON_Mapper : process_jason_basename_mismatch - Index offset craziness: base file %s %d", base_numbering_file, joffset)
                        else:
                            logging.debug("JSON_Mapper : process_jason_basename_mismatch - Numbered file success %d %s %s", index, checkm, checkj)
                            if checkm not in self.mapper:
                                self.mapper[checkm] = checkj
                            else:
                                if self.mapper[checkm] != checkj:
                                    logging.error("JSON_Mapper : process_jason_basename_mismatch - hmm, json mapper already has different entry media %s json %s mapper has %s", checkm, checkj, self.mapper[checkm])
                    elif media_exists or json_exists:
                        # either a json file exists solo or a media file exists solo - either way, this isn't what we want ideally
                        logging.error("JSON_Mapper : process_jason_basename_mismatch - Numbered file fail at %d %s %s", index, checkm, checkj)
                    else:
                        if index==0:
                            # We've found a bug somewhere, because we started this little odyssey with a file with a nummbered extension, but failed
                            # to find the zeroth example. Stop, look, debug.
                            logging.error("JSON_Mapper : process_jason_basename_mismatch - Numbered file fail at zero %d %s %s", index, self.json_basename_noext, self.target_media_filename_truncated, checkj, checkm)
                            sys.exit(1)
                        # This is the expected path when we reach the end of the file numbering fun - we run out of files and go back to work
                        #logging.debug("Numbered file break at %d %s", index, base_numbering_file)
                        break

            else:
                # if we remove the (1) numbering from the file, and we still don't match what is in the json file
                # this is a bug that needs investigation so stop
                logging.error("JSON_Mapper : process_jason_basename_mismatch - Numbered MISMATCH json %s with target %s %s %s", self.json_basename_noext, self.target_media_filename, base_numbering_file, self.target_media_filename_truncated)
                sys.exit(1)
            pass
        else:
            logging.error("JSON_Mapper : process_jason_basename_mismatch - Mismatch json %s with target %s", self.json_basename_noext, self.target_media_filename)
            sys.exit(1)

    def process_json(self):
        # Open the json file and read it
        with open(self.json_filename) as f:
            self.json_document = json.load(f)
            logging.debug("JSON_Mapper : process_json - json doc %s", self.json_document)
        # Perform various manipulations on the target media filename from the json
        self.process_target_media_filename()
        # Normally the json basename (input_file.jpg.json with .json removed) should simply
        # match the target media file (input_file.jpg)
        if self.target_media_filename_truncated==self.json_basename_noext:
            logging.debug("JSON_Mapper : process_json - basename match %s", self.json_basename_noext)
            self.process_json_basename_match()
        else:
            # But there are lots of cases where this simply isn't true
            logging.debug("JSON_Mapper : process_json - basename mismatch %s", self.json_basename_noext)
            self.process_json_basename_mismatch()

class Media_Sifter:
    '''
        Class to manage the high level media sifting process. Given a top level folder, an
        output folder and a report name, it will recursively process all folders of media 
        within the input, generating a json report file that proposes what file changes
        should be made and metadata used to copy the input to the output.
    '''
    def __init__(self, input_folder, output_folder, report_filename):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.report_filename = report_filename
        self.report = {}

    def sift_media_in_subfolder(self):
        logging.info("Media_Sifter : sift_media_in_subfolder - Processing folder %s", self.current_folder)

        match_year_in_folder_name = re.compile(r".*/.*([12]\d\d\d)$", re.I)
        match = match_year_in_folder_name.match(self.current_folder)
        if match:
            year = int(match.group(1))
        else:
            year = None

        # Before we do anything, create a mapping of all json files to image files
        # in the current folder, resolving any conflicts as we go
        mapper_maker = JSON_Mapper(self.current_folder)
        json_mapper = mapper_maker.create_mapper()

        processor = File_Processor(json_mapper, year, self.output_folder)

        #   for each photo or video file supported:
        for source_file in glob.iglob(self.current_folder + "//*", recursive=False):
            if source_file in self.report:
                logging.debug("Media_Sifter : sift_media_in_subfolder - skipping %s", source_file)
                continue    
            results = processor.process_file(source_file)
            if results:
                logging.debug("Media_Sifter : sift_media_in_subfolder - %s", results)
                self.report[source_file] = results
                self.json_fh.write(json.dumps(results, default=str)+',\n')
                self.json_fh.flush()

    def read_report(self):
        report = []
        if os.path.isfile(self.report_filename):
            with open(self.report_filename) as json_fh:
                report = json.load(json_fh)
        for entry in report:
            self.report[entry['source']] = entry
    
    def sift_media(self):
        # If the report file already exists, read the contents into a hashmap using the source element as the key.
        # Then use this hashmap to skip files already processed.
        self.read_report()

        # Open report file as a json for writing - append mode
        with open(self.report_filename, 'a') as self.json_fh:
            self.json_fh.write('[\n')
            # recurse over all subdirectories
            for search_path in glob.iglob(self.input_folder + '/**', recursive=True):
                if os.path.isdir(search_path): # filter dirs
                    self.current_folder = search_path
                    self.sift_media_in_subfolder()
            self.json_fh.write(']\n')

    def enact_report(self):
        # Use the hashmap report to actually copy and update files to their new destination
        # For each line in the report:
        # - Check if the output file already exists
        # - <maybe> If the file already exists, do a simplistic check to see if it is the same file contents
        # - If the filename isn't unique, add some uniqueness to the filename
        # - Copy the file from source to destination, creating any missing folders in the path
        # - Update the file modification timestamp
        # - Update missing exif data if needed
        pass

parser = argparse.ArgumentParser(
                    prog='takeout_fixer_sifter',
                    description='Sort photos and videos into subfolders by exif data and modification time ',
                    epilog='Text at the bottom of help')
parser.add_argument('infolder')           # positional argument
parser.add_argument('outfolder')           # positional argument
parser.add_argument('report')
parser.add_argument('-n', '--dryrun', action='store_true') 
parser.add_argument('-d', '--debug', action='store_true') 
args = parser.parse_args()
if args.debug:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.getLogger().setLevel(logging.INFO)

sifter = Media_Sifter(args.infolder, args.outfolder, args.report)
sifter.sift_media()
if not args.dryrun:
    sifter.enact_report()   
