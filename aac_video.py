import sys
import os
from PIL import Image, ImageOps
import cv2 as cv
# import numpy as np
import svgwrite as svg
from tqdm import tqdm

ERRORS = {
    "invalid_ext": "Not a valid file extension.",
    "missing_path": "Must provide video path.",
    "video_read": "Cannot read frame from video stream."
}

VALID_EXTS = ('.mp4', '.jpg', 'jpeg', '.png')
MAXWIDTH = 80 # number of characters per line
STYLEBIAS = 2.5 # adjust aspect ratio based on font and line formatting (terminal-dependent)
OUTRES = (1280,720)
FPS = 30

ascii_map = ".^,:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$" # revised from https://stackoverflow.com/a/66140774 without escape-chars
normalize = lambda x: ((x/255)*(len(ascii_map)-1)).astype(int)

def write_file(frames, fname):
    fourcc = cv.VideoWriter_fourcc(*'XVID')
    with cv.VideoWriter(fname, fourcc, FPS, OUTRES) as output:
        frames_to_write = tqdm(frames, desc='writing frames to file')
        for frame in frames_to_write:
            output.write(frame)

def load_file(fpath):
    # check file extension
    fname = os.path.basename(fpath)
    fext = os.path.splitext(fname)[1].lower()
    frames = []
    if fext not in VALID_EXTS:
        exit(ERRORS["invalid_ext"])
    elif fext == '.mp4':
        with cv.VideoCapture(fpath) as data:
            while(data.isOpened()):
                ret, frame = data.read()
                if not ret:
                    exit(ERRORS["video_read"])
                frames.append(frame)
    else:
        frames.append(cv.imread(fpath))
    return frames

def convert(frames, resize=True):
    frames_to_convert = tqdm(frames, desc='converting frames')
    for frame in frames_to_convert:
        #convert to grayscale
        image_raw = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

        # resize image based on # ascii chars per row
        if resize:
            new_dims = (MAXWIDTH,round(MAXWIDTH/(STYLEBIAS*(frame.shape[0]/frame.shape[1]))))
            image_tmp = cv.resize(image_raw, new_dims, interpolation=cv.INTER_LINEAR)
        else:
            image_tmp = image_raw

        # convert pixels to normalized ascii range
        image = normalize(image_tmp)

        # TODO: actual conversion to ascii
        # SVG? PNG? numpy array -> PNG?

if __name__ == '__main__':
    data = load_file(sys.argv[1])
