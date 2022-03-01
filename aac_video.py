from curses import meta
import sys
import os
from tkinter import CHAR
from xml.sax.handler import property_encoding
from PIL import Image as im
from PIL import ImageOps as imops
from PIL import ImageDraw as imdraw
from PIL import ImageFont as imfont
import cv2 as cv
import numpy as np
from tqdm import tqdm

ERRORS = {
    "invalid_ext": "Not a valid file extension.",
    "missing_path": "Must provide video path.",
    "video_read": "Cannot read frame from video stream."
}

OUTNAME = 'out.mp4'
FONTS_PATH = '/usr/share/fonts/truetype/ubuntu/'
FONT = 'Ubuntu-M.ttf'
VALID_EXTS = ('.mp4', '.m4v', '.avi')
RES_X = 128
RES_Y = 72
CHAR_SCALE = 0.1
CHAR_PIXEL_SIZE = 10
OUTRES = (RES_Y*CHAR_PIXEL_SIZE,RES_X*CHAR_PIXEL_SIZE)
FPS = 24

# https://docs.opencv.org/3.4/d4/d15/group__videoio__flags__base.html#gaeb8dd9c89c10a5c63c139bf7c4f5704d

ascii_map = " .^,:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$" # revised from https://stackoverflow.com/a/66140774 without escape-chars
normalize = lambda x: ((x/255)*(len(ascii_map)-1)).astype(np.uint8)

def get_font(fontpath, basesize):
    return imfont.truetype(fontpath, size=basesize, encoding='unic')

def preload_rasters(font):
    '''
    desc: for each glyph in a font, create a raster for it
    params:
        font = font class from file
    return: array of char rasters
    '''

    return np.array([rasterize_char(char, font, CHAR_PIXEL_SIZE) for char in ascii_map])

def write_file(frames, fname, fps):
    '''
    desc: write frames to video
    params:
        frames = list of arrays containing frames of video
        fname = output file name (ext included)
        fps = fps of output (should be the same as input)
    return: none (outfile written to fs)
    '''

    fourcc = cv.VideoWriter_fourcc(*'mp4v')
    output = cv.VideoWriter(fname, fourcc, fps, OUTRES[::-1], False)
    frames_to_write = tqdm(frames, desc='writing frames to file')

    for frame in frames_to_write:
        output.write(frame)
    output.release()

def load_file(fpath):
    '''
    desc: load video file
    params:
        fpath = absolute path to video file
    return: array of (raw) frames from video
    '''

    fname = os.path.basename(fpath)
    fext = os.path.splitext(fname)[1].lower()
    frames = []
    if fext not in VALID_EXTS:
        raise NotImplementedError(ERRORS["invalid_ext"])

    data = cv.VideoCapture(fpath)
    for i in range(int(data.get(cv.CAP_PROP_FRAME_COUNT))):
        ret, frame = data.read()
        if not ret:
            raise ValueError(ERRORS["video_read"])

        frames.append(frame)

    properties = {
        'fps': int(data.get(cv.CAP_PROP_FPS)),
        'width': int(data.get(cv.CAP_PROP_FRAME_WIDTH)),
        'height': int(data.get(cv.CAP_PROP_FRAME_HEIGHT)),
    }
    metaproperties = {
        'c_res_x': int(properties['width']*CHAR_SCALE),
        'c_res_y': int(properties['height']*CHAR_SCALE),
        'c_pixel_size': properties['width']//int(properties['width']*CHAR_SCALE)
    }
    properties.update(metaproperties)

    data.release()
    return frames, properties

def rasterize_char(char, font, size, color=None):
    '''
    desc: rasterize a character or "glyph" from a font as a (size x size) array
    params:
        char = single-char string, must exist in font's glyphmap
        font = loaded font class from file
        size = width & height of char raster, in pixels
        color = TODO
    return: raster as array
    '''

    # TODO: RGB

    width, height = font.getsize(char)
    offset = ((size-width)//2, (size-height))
    bg = (0,0,0) if color else 0
    cmode = 'RGB' if color else 'L'
    fill = color if color else 255

    canvas = im.new(cmode, (size,size), color=bg)
    drawn = imdraw.Draw(canvas)
    drawn.text(offset, char, font=font, fill=fill)

    return np.array(canvas)

def convert(frames, properties, font, resize=True):
    '''
    desc: convert frames to ascii-fied version using a given font
    params:
        frames = array of raw video frames
        properties = video metadata
        font = font class from file
        resize = whether conversion is done on downscaled version of frames or raw frames' pixels
    return: list of converted frame arrays
    '''

    frames_to_convert = tqdm(frames, desc='converting frames')
    new_frames = []
    charmap = preload_rasters(font)

    c_res = (properties['c_res_y'], properties['c_res_x'])
    res = (properties['height'], properties['width'])

    for frame in frames_to_convert:
        image_raw = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        image_tmp = cv.resize(image_raw, c_res[::-1]) if resize else image_raw
        image = normalize(image_tmp)

        canvas = np.zeros(res)
        tmp = np.array([charmap[pixel] for row in image for pixel in row])
        canvas = np.vstack([np.hstack(tmp[i*c_res[1]:(i+1)*c_res[1]]) for i in range(c_res[0])])

        new_frames.append(canvas)

    return new_frames

if __name__ == '__main__':
    if len(sys.argv) < 2:
        exit("Must provide image path.")

    frames, properties = load_file(sys.argv[1])
    font = get_font(FONTS_PATH+FONT, properties['c_pixel_size'])
    out = convert(frames, properties, font)
    write_file(out, OUTNAME, properties['fps'])