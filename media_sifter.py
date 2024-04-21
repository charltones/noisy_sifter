import os
import re
import glob
import json
import shutil
import logging
from json_mapper import JSON_Mapper, JSONMapperFatalException
from file_processor import File_Processor

logger = logging.getLogger(__name__)

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
        self.hasher = {}
        self.hash_collisions = {}

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
        try:
            json_mapper = mapper_maker.create_mapper()
        except JSONMapperFatalException as e:
            logging.error("Media_Sifter : sift_media_in_subfolder - fatal exception %s", e)
            return

        processor = File_Processor(json_mapper, year, self.output_folder)

        #   for each photo or video file supported:
        for source_file in glob.iglob(self.current_folder + "//*", recursive=False):
            if os.path.isdir(source_file): # filter dirs
                continue

            if source_file in self.report:
                logging.debug("Media_Sifter : sift_media_in_subfolder - skipping %s", source_file)
                continue    
            results = processor.process_file(source_file)
            if results:
                logging.debug("Media_Sifter : sift_media_in_subfolder - %s", results)
                self.report[source_file] = results
                if results['hash'] is not None:
                    if results['hash'] in self.hasher:
                        logging.warning("Media_Sifter : sift_media_in_subfolder - hash collision %s %s clashes with %s",
                                        results['hash'], self.hasher[results['hash']], source_file)
                    else:    
                        self.hasher[results['hash']] = source_file
                else:
                    logging.debug("Media_Sifter : sift_media_in_subfolder - unhashable %s", source_file)
                self.json_fh.write(json.dumps(results, default=str)+',\n')
                self.json_fh.flush()

    def get_backup_filename(self, input_file):
        # create a backup filename by appending a number to the end of the input file name
        # until we find a filename that doesn't exist
        backup_filename = input_file
        backup_number = 1
        base, extension = os.path.splitext(backup_filename)
        while os.path.isfile(backup_filename):
            backup_filename = base + '(' + str(backup_number) + ')' + extension
            backup_number += 1
        return backup_filename
    
    def add_collision(self, hash, source):
        if hash in self.hash_collisions:
            self.hash_collisions[hash].append(source)
        else:
            self.hash_collisions[hash] = [self.hasher[hash], source]

    def read_report(self, backup=True):
        # if the report already exists, read its contents, then move it to a numbered backup
        report = []
        if os.path.isfile(self.report_filename):
            logging.info("Media_Sifter : read_report - reading existing report file %s", self.report_filename)
            with open(self.report_filename) as json_fh:
                report = json.load(json_fh)
            for entry in report:
                if 'source' in entry:
                    self.report[entry['source']] = entry
                    if 'hash' in entry and entry['hash'] is not None:
                        if entry['hash'] in self.hasher:
                            logging.debug("Media_Sifter : read_report - hash collision %s %s clashes with %s",
                                             entry['hash'], self.hasher[entry['hash']], entry['source'])
                            self.add_collision(entry['hash'], entry['source'])
                        else:    
                            self.hasher[entry['hash']] = entry['source']
                    else:
                        logging.debug("Media_Sifter : read_report - null or missing hash %s",
                                            entry['source'])

            if backup:
                # move the report file to a numbered backup
                backup_filename = self.get_backup_filename(self.report_filename)
                logging.info("Media_Sifter : read_report - backing up existing report file %s", backup_filename)
                os.rename(self.report_filename, backup_filename)        
    
    def sift_media(self):
        # If the report file already exists, read the contents into a hashmap using the source element as the key.
        # Then use this hashmap to skip files already processed.
        self.read_report()

        # Open report file as a json for writing - append mode
        with open(self.report_filename, 'a') as self.json_fh:
            self.json_fh.write('[\n')
            if len(self.report) != 0:
                # if the report file already exists, we need to write out all the existing report entries
                logging.debug("Media_Sifter : sift_media - writing existing report entries")
                for entry in self.report:
                    self.json_fh.write(json.dumps(self.report[entry], default=str)+', \n')  
                self.json_fh.flush()
            # recurse over all subdirectories
            for search_path in glob.iglob(self.input_folder + '/**', recursive=True):
                if os.path.isdir(search_path): # filter dirs
                    self.current_folder = search_path
                    self.sift_media_in_subfolder()
            self.json_fh.write('{}]\n')

    def clean_destinations(self, destinations):
        # Given a set of destinations [a, b, c, d] see if the set can be simplified by removing
        # certain strings from the end of the destination, e.g.
        # ['file.jpg', 'file(1).jpg', 'file(2).jpg'] and ['file(3)(1).jpg', 'file(3).jpg']
        # ['file(4).jpg', 'file(1).jpg', 'file(2).jpg']
    
        # get the common file extension from all destinations
        exts = set([os.path.splitext(n)[1] for n in destinations])
        if len(exts) != 1:
            # not all destinations have the same extension
            logging.error("Media_Sifter : clean_destinations - destinations with different extensions %s", destinations)
            return destinations
        ext = list(exts)[0] 
        # look for the shortest basename (without extension) in the destinations 
        bases = sorted([os.path.splitext(n)[0] for n in destinations], key=len)
        # if there are multiple shortest basenames, we need to disambiguate
        base_lengths = [len(b) for b in bases if len(b) == len(bases[0])]
        if len(base_lengths) > 1:
            # if there are multiple bases of same length, pick first and remove last set of brackets
            m = re.match(r'^(.*)(\([^\(]+\))$', bases[0])
            if m:
                base = m.group(1)
            else:
                base = bases[0]            
        else:
            base = bases[0]
        # check if all destinations contain this substring
        if all([n.startswith(base) for n in destinations]):
            # remove the base from the destinations
            new_dests = [base+ext]
            logging.debug("Media_Sifter : clean_destinations - destinations %s becomes %s", destinations, new_dests)
            return new_dests
        else:
            logging.info("Media_Sifter : clean_destinations - destinations %s not cleaned", destinations)
            return destinations

    def analyse_report(self):
        # Analyse the generated report and look for inconsistencies or anything that needs 
        # addressing

        # Read the report but don't back it up as we're not making changes
        self.read_report(backup=False)

        # Loop through all the entries in the report
        destination_lookup = {}
        for entry in self.report:
            # Check 1. Are there multiple output files with same filename?
            destination = self.report[entry]['destination']
            if destination in destination_lookup:
                # Two entries in the report, from two different sources, have the same destination
                # Now check if they have the same hash
                if self.report[entry]['hash'] == self.report[destination_lookup[destination]]['hash']:
                    # This is fine - same hash, same photo, we should be able to discard one
                    pass
                else:
                    # We have entries with different hashes that clash on the destination filename
                    # We will update the report output name to disambiguate them
                    logging.warning("Media_Sifter : analyse_report - destination collision %s %s clashes with %s",
                                    destination, destination_lookup[destination], entry)
            else:
                destination_lookup[destination] = self.report[entry]['source']
            
            # Check 2. for date inconsistencies - e.g. one particular camera with date set wrong
            # Compare exif date, filename date, folder year and json date
            # Check that the chosen preferred date is the right one
            pass # todo

            # Check 3. if there is exif data that needs updating
            # GPS, date
            pass # todo

        # Check 4. and loop through all hash collisions
        for hash in self.hash_collisions:
            destinations = [self.report[s]['destination'] for s in self.hash_collisions[hash]]
            destinations = self.clean_destinations(destinations)
            # Do they all have the same output filename?
            if len(set(destinations)) == 1:
                pass
            else:
                # Some of these can be fixed by 'cleaning' the output file to remove '(n)' additions
                logging.warning("Media_Sifter : analyse_report - multiple destinations for same hash, entry %s",
                                 set(destinations))
                # Do they all have the same metadata?
                # Can we choose a 'best' copy to source from?
                pass # todo

    def enact_report(self):
        # Use the hashmap report to actually copy and update files to their new destination
        for source in self.report:
            logging.debug("Media_Sifter : enact_report - %s", source)
            if 'destination' in self.report[source]:
                destination = self.report[source]['destination']
                if os.path.isfile(source):
                    # if the source file exists, copy it to the destination
                    # check if the destination file exists
                    if os.path.isfile(destination):
                        # - <maybe> If the file already exists, do a simplistic check to see if it is the same file contents
                        # - if the destination file exists, check if it is the same file contents
                        # - if the destination file exists and is different, rename it to a numbered backup
                        logging.warning("Media_Sifter : enact_report - destination file %s exists", destination)
                        pass
                    else:
                        # Copy the file from source to destination, creating any missing folders in the path
                        logging.info("Media_Sifter : enact_report - copying %s to %s", source, destination)
                        os.makedirs(os.path.dirname(destination), exist_ok=True)
                        shutil.copy(source, destination)                        
                        
                        # Update the file modification timestamp
                        os.utime(destination, (self.report[source]['preferred_ts'], self.report[source]['preferred_ts']))

        # - <todo> Update missing exif data if needed
        pass
