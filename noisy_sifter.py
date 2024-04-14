#!/usr/bin/python3

import argparse
import logging
import logging.handlers
from pillow_heif import register_heif_opener
from media_sifter import Media_Sifter

logger = logging.getLogger(__name__)
logging.basicConfig(
    handlers=[
        logging.handlers.RotatingFileHandler('noisy_sifter.log', maxBytes=75000000, backupCount=10),
        logging.StreamHandler()
    ],
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
# Allow PIL to open HEIC files
register_heif_opener()

parser = argparse.ArgumentParser(
                    prog='takeout_fixer_sifter',
                    description='Sort photos and videos into subfolders by exif data and modification time ',
                    epilog='Text at the bottom of help')
parser.add_argument('infolder')           # positional argument
parser.add_argument('outfolder')           # positional argument
parser.add_argument('report')
parser.add_argument('-s', '--scan', action='store_true') 
parser.add_argument('-a', '--analyse', action='store_true') 
parser.add_argument('-d', '--debug', action='store_true') 
args = parser.parse_args()
if args.debug:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.getLogger().setLevel(logging.INFO)

sifter = Media_Sifter(args.infolder, args.outfolder, args.report)
if args.scan:
    sifter.sift_media()
elif args.analyse:
    sifter.analyse_report()
elif args.copyfiles:
    sifter.enact_report()
else:
    logging.error("Noisy_Sifter : no action specified : "
                  "use --scan to sift media, --analyse to check an existing report or "
                  "--copyfiles to actually copy files to output folder")
