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
        logging.warning("Error converting value in %s to a date", instr)
    return None

def is_exif(ext):
    return ext.lower() in ext_exif

def is_json(ext):
    return ext in ext_json

def get_metadata(candidate, year, json_mapper):
    # Look for exif data already existing
    datetimeexif = None
    datetimeexifs = None
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_metadata(candidate)
        for d in metadata:
            if "EXIF:DateTimeOriginal" in d:
                datetimeexifs = d["EXIF:DateTimeOriginal"]
                break
            elif "QuickTime:CreateDate" in d:
                datetimeexifs = d["QuickTime:CreateDate"]
                break
    if datetimeexifs:
        datetimeexif = find_date(datetimeexifs)
    if year:
        if datetimeexif and datetimeexif.date().year != year:
            logging.error("Sense check failed for year %d candidate %s datetimeexif %s", year, candidate, datetimeexif)

    # Look for datetime in filename itself
    datetimefilename = find_date(os.path.basename(candidate))
    if year:
        if datetimefilename and datetimefilename.date().year != year:
            logging.error("Sense check failed for year %d candidate %s datetimefilename %s", year, candidate, datetimefilename)

    # Look for a matching json file
    base_candidate = os.path.basename(candidate)
    datetimejson = None
    if base_candidate in json_mapper:
        testjson = os.path.dirname(candidate)+"/"+json_mapper[base_candidate]
        with open(testjson) as f:
            d = json.load(f)
        datetimejsonts = d['photoTakenTime']['timestamp']
        datetimejson = datetime.datetime.fromtimestamp(int(datetimejsonts))
    else:
        logger.warning("No json file for %s", candidate)
    if year:
        if datetimejson and datetimejson.date().year != year:
            logging.error("Sense check failed for year %d candidate %s datetimejson %s", year, candidate, datetimejson)

    # <todo> Look for being in a sequence of files that otherwise had datetime
    # Look at the year folder that we are in
    logging.debug("Candidate %s exif says %s file says %s json says %s", candidate, datetimeexif, datetimefilename, datetimejson)
    if datetimeexif:
        return datetimeexif
    elif datetimejson:
        return datetimejson
    elif datetimefilename:
        logging.warning("Resorting to filename based year %s %s", candidate, datetimefilename)
        return datetimefilename
    else:
        # oops - the triple missing scenario
        logging.error("No metadata found for %s", candidate)
        return None

def create_json_mapper(infolder):
    # find all json files in the specified folder
    # open the file and read the details into a hashmap
    json_mapper = {}
    # try to identify the source file
    # needs some cleverness to work out when multiple files have same name!
    for jsonfile in glob.iglob(infolder + "//*.json", recursive=False):
        # We're not interested in metadata*.json
        if re.match(r"metadata.*", os.path.basename(jsonfile)):
            pass
        else:
            #logging.debug("create_json_mapper: %s", jsonfile)
            with open(jsonfile) as f:
                d = json.load(f)
            target = d['title']
            tfile, text = os.path.splitext(target)

            if len(target) > 46:
                add_text = True
            else:
                if len(text)==0:
                    # Google what the actual?
                    # Sometimes the json file target filename has no extension, but the media file is a jpg?!
                    text = '.jpg'
                    add_text = True
                else:
                    add_text = False
            # replace ' in title with _ and truncate to 46 characters
            # why? You'll need to ask Google
            trunc_target = target.replace('\'', '_')[:46]

            jfile, jext = os.path.splitext(jsonfile)
            jfile = os.path.basename(jfile)
            if trunc_target==jfile:
                # most of the time the image file for image.ext is image.ext.json
                # now need a sanity check on the contents just in case

                # if our 46 character truncation chops the middle of our file extension, then remove it
                m = re.match(r"^(.*)\..?.?$", trunc_target)
                if m:
                    trunc_target = m.group(1)
                media_file = trunc_target
                if add_text:
                    media_file += text
                if os.path.isfile(infolder+'/'+media_file):
                    json_mapper[media_file] = os.path.basename(jsonfile)
                else:
                    # try 47 characters?
                    if add_text:
                        media_file =  target.replace('\'', '_')[:47]+text
                    if os.path.isfile(infolder+'/'+media_file):
                        logging.warning("47 char fun and games %s", media_file)
                        json_mapper[media_file] = os.path.basename(jsonfile)
                    else:
                        # sometimes google exports a json file with no corresponding media file
                        # most of the time these can be found in other album folders though
                        logging.error("Expected media file not found %s", media_file)
                #logging.debug("Simple match json %s with target %s", jsonfile, target)
            else:
                m = re.match(r"(.*)\.\w{1,4}\(\d+\)$", jfile)
                if m:
                    # if there are multiple files with the same name they can be renamed
                    # so image.ext becomes image(1).ext

                    # we still need to match up the numbered files to resolve ambiguities
                    base_numbering_file = m.group(1)
                    # the target media file doesn't have truncated file extensions in it, but the json does!
                    m = re.match(r"^(.*)\.\w{1,2}$", trunc_target)
                    if m:
                        trunc_target = m.group(1)
                    if add_text:
                        trunc_target += text

                    if base_numbering_file+text==trunc_target:
                        joffset = 0
                        # check all the numbered json files and media files line up correctly
                        for index in range(20):
                            if index==0:
                                checkm = base_numbering_file+text
                                checkj = base_numbering_file+text+jext
                            else:
                                checkm = "{}({}){}".format(base_numbering_file,index,text)
                                checkj = "{}{}({}){}".format(base_numbering_file,text,index+joffset,jext)
                            media_exists = os.path.isfile(infolder+'/'+checkm)
                            json_exists = os.path.isfile(infolder+'/'+checkj)
                            if media_exists and json_exists:
                                checkj2 = "{}({}){}{}".format(base_numbering_file,index,text,jext)
                                json2_exists = os.path.isfile(infolder+'/'+checkj2)
                                if json2_exists:
                                    # if there was actually a media file uploaded called image(1).ext and google wants to write a second
                                    # image(1).ext, then it will have the first as image(1).ext -> image(1).ext.json (note position of
                                    # number) and then write out the second as image(2).ext -> image.ext(1).json
                                    # Because of this corner case, we need to record a json file index offset, as the media file and
                                    # json file index will get out of sync after this. We also don't want to cross match the wrong
                                    # media and json files, so we don't record this 'match' and skip to the next index
                                    joffset -= 1
                                    logging.warning("Index offset craziness: base file %s %d", base_numbering_file, joffset)
                                else:
                                    #logging.debug("Numbered file success %d %s %s", index, checkm, checkj)
                                    if checkm not in json_mapper:
                                        json_mapper[checkm] = checkj
                                    else:
                                        if json_mapper[checkm] != checkj:
                                            logging.error("hmm, json mapper already has different entry media %s json %s mapper has %s", checkm, checkj, json_mapper[checkm])
                            elif media_exists or json_exists:
                                # either a json file exists solo or a media file exists solo - either way, this isn't what we want ideally
                                logging.error("Numbered file fail at %d %s %s", index, checkm, checkj)
                            else:
                                if index==0:
                                    # We've found a bug somewhere, because we started this little odyssey with a file with a nummbered extension, but failed
                                    # to find the zeroth example. Stop, look, debug.
                                    logging.error("Numbered file fail at zero %d %s %s", index, jfile, trunc_target, checkj, checkm)
                                    sys.exit(1)
                                # This is the expected path when we reach the end of the file numbering fun - we run out of files and go back to work
                                #logging.debug("Numbered file break at %d %s", index, base_numbering_file)
                                break

                    else:
                        # if we remove the (1) numbering from the file, and we still don't match what is in the json file
                        # this is a bug that needs investigation so stop
                        logging.error("Numbered MISMATCH json %s with target %s %s %s", jfile, target, base_numbering_file, trunc_target)
                        sys.exit(1)
                    pass
                else:
                    logging.error("Mismatch json %s with target %s", jfile, target)
                    sys.exit(1)
    return json_mapper

def sift_media(infolder, outfolder, dryrun):
    # recurse over all subdirectories
    dirmatch = re.compile(r".*/.*(\d\d\d\d)$", re.I)
    for filename in glob.iglob(infolder + '/**', recursive=False):
        if os.path.isdir(filename): # filter dirs
            match = dirmatch.match(filename)
            if match:
                year = int(match.group(1))
            else:
                year = None

            logging.info("Processing folder %s, year %s", filename, year)
            
            # Before we do anything, create a mapping of all json files to image files
            # resolving any conflicts as we go
            jsonmapper = create_json_mapper(filename)

            #   for each photo or video file supported:
            for candidate in glob.iglob(filename + "//*", recursive=False):
                cfile, cext = os.path.splitext(candidate)
                if is_exif(cext):
                    metadata = get_metadata(candidate, year, jsonmapper)
                    if metadata:
                        logging.debug("got metadata: %s %s", candidate, metadata.isoformat())
                        # come up with a proposed new name for the file
                        outfile = "{0}/{1:%Y}/{1:%Y}_{1:%m}/{1:%Y-%m-%d_%H%M%S}_{2}".format(outfolder, metadata, os.path.basename(candidate))
                        if not dryrun:
                            # actually create a new copy
                            logging.info("Copy to output %s", outfile)

                            # todo - actually copy the file
                            # todo - correct the file modification time
                            pass
                        else:
                            logging.info("DRYRUN: output would be %s", outfile)
                    else:
                        logging.error("no metadata: %s", candidate)
                elif is_json(cext):
                    pass
                else:
                    ftype = magic.from_file(candidate, mime=True)
                    logging.error("Found an extension I don't like: %s %s (mime type is %s)", cfile, cext, ftype)

    #     read exif tag (if exists)
    #     read json file (if can be found, need some heuristics as inconsistent naming)
    #     look for date time in filename
    #     determine the best shot at 'photo taken time' from available sources
    #     determine latlong if available
    #     determine country and timezone from latlong if possible
    #     if an exif supporting file:
    #       update exif photo taken
    #       update latlong if missing
    #     if a video or other supported file:
    #       copy file to $outputDir/$year/$year_$month/$datetime_origFilename.ext
    #       set file modification time to photo taken time
    #     if error:
    #       log report of what happened

#get_metadata("Takeout/Google Photos/Photos from 2017/5182EA1F-A62C-4AF8-B463-CC6D81B24B2A-3605-00000.png", 2017)
parser = argparse.ArgumentParser(
                    prog='takeout_fixer_sifter',
                    description='Sort photos and videos into subfolders by exif data and modification time ',
                    epilog='Text at the bottom of help')
parser.add_argument('infolder')           # positional argument
parser.add_argument('outfolder')           # positional argument
parser.add_argument('-n', '--dryrun', action='store_true') 
parser.add_argument('-d', '--debug', action='store_true') 
args = parser.parse_args()
if args.debug:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.getLogger().setLevel(logging.INFO)

sift_media(args.infolder, args.outfolder, args.dryrun)