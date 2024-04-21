import glob
import os
import re
import logging
import json
import sys

class JSONMapperFatalException(Exception):
    pass

class JSON_Mapper:
    '''
        Class which processes a folder of media files which also may contain json sidecar files. It 
        attempts to map the media files to the corresponding json files. This process is complex
        due to the generally buggy way that Google has implemented Takeout for photos.
    '''
    def __init__(self, input_folder):
        self.input_folder = input_folder
        self.mapper = {}

    def is_a_metadata_sidecar(self):
        for required in ['title', 'description', 'imageViews']:
            if required not in self.json_document:
                return False
        return True
    
    def create_mapper(self):
        # find all json files in the specified input folder
        # open the file and read the details into a hashmap
        # try to identify the mapping from json file to target media file
        # needs some cleverness to work out when multiple files have same name!
        for json_filename in glob.iglob(self.input_folder + "//*.json", recursive=False):
            self.json_filename = json_filename
            self.json_basename = os.path.basename(json_filename)
            self.json_basename_noext, self.json_fileext = os.path.splitext(self.json_basename)
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
            m = re.match(r"^(.*)(\.\w{1,2})$", self.target_media_filename_truncated)
            if m:
                logging.debug("target media file doesn't have truncated file extensions in it, but the json does! %s", self.target_media_filename_truncated)
                self.target_media_filename_truncated = m.group(1)
                self.target_media_fileext_for_json = m.group(2)
            else:
                self.target_media_fileext_for_json = self.target_media_fileext
            if self.add_file_extension:
                self.target_media_filename_truncated += self.target_media_fileext

            if base_numbering_file+self.target_media_fileext==self.target_media_filename_truncated:
                joffset = 0
                # check all the numbered json files and media files line up correctly
                for index in range(20):
                    if index==0:
                        checkm = base_numbering_file+self.target_media_fileext
                        checkj = base_numbering_file+self.target_media_fileext_for_json+self.json_fileext
                    else:
                        checkm = "{}({}){}".format(base_numbering_file,index,self.target_media_fileext)
                        checkj = "{}{}({}){}".format(base_numbering_file,self.target_media_fileext_for_json,index+joffset,self.json_fileext)
                    media_exists = os.path.isfile(self.input_folder+'/'+checkm)
                    json_exists = os.path.isfile(self.input_folder+'/'+checkj)
                    if media_exists and json_exists:
                        checkj2 = "{}({}){}{}".format(base_numbering_file,index,self.target_media_fileext_for_json,self.json_fileext)
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
                            raise JSONMapperFatalException
                        # This is the expected path when we reach the end of the file numbering fun - we run out of files and go back to work
                        #logging.debug("Numbered file break at %d %s", index, base_numbering_file)
                        break
            else:
                # if we remove the (1) numbering from the file, and we still don't match what is in the json file
                # this is a bug that needs investigation so stop
                logging.error("JSON_Mapper : process_jason_basename_mismatch - Numbered MISMATCH json %s with target %s %s %s", self.json_basename_noext, self.target_media_filename, base_numbering_file, self.target_media_filename_truncated)
                raise JSONMapperFatalException
            pass
        else:
            logging.error("JSON_Mapper : process_jason_basename_mismatch - Mismatch json %s with target %s", self.json_basename_noext, self.target_media_filename)
            raise JSONMapperFatalException

    def process_json(self):
        # Open the json file and read it
        with open(self.json_filename) as f:
            self.json_document = json.load(f)
            if self.is_a_metadata_sidecar():
                logging.debug("JSON_Mapper : process_json - json doc %s", self.json_document)
            else:
                logging.debug("JSON_Mapper : process_json - skipping json doc %s", self.json_document)
                return
        # Perform various manipulations on the target media filename from the json
        self.process_target_media_filename()
        # Normally the json basename (input_file.jpg.json with .json removed) should simply
        # match the target media file (input_file.jpg)
        if self.target_media_filename_truncated==self.json_basename_noext:
            logging.debug("JSON_Mapper : process_json - basename match %s", self.json_basename_noext)
            self.process_json_basename_match()
        else:
            # But there are lots of cases where this simply isn't true
            logging.debug("JSON_Mapper : process_json - basename mismatch %s with %s", self.json_basename_noext, self.target_media_filename_truncated)
            self.process_json_basename_mismatch()