import sys
import os
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

FONTS_PATH = '/usr/share/fonts/truetype/ubuntu/'
FONT = 'Ubuntu-M.ttf'
VALID_EXTS = ('.mp4', '.m4v', '.avi')
RES_X = 128
RES_Y = 72
CHAR_PIXEL_SIZE = 10
OUTRES = (RES_X*CHAR_PIXEL_SIZE,RES_Y*CHAR_PIXEL_SIZE)
FPS = 24

ascii_map = " .^,:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$" # revised from https://stackoverflow.com/a/66140774 without escape-chars
normalize = lambda x: ((x/255)*(len(ascii_map)-1)).astype(np.uint8)

def write_file(frames, fname):
    fourcc = cv.VideoWriter_fourcc(*'mp4v')
    output = cv.VideoWriter(fname, fourcc, FPS, OUTRES, False)
    frames_to_write = tqdm(frames, desc='writing frames to file')
    for frame in frames_to_write:
        output.write(frame)
    output.release()

def load_file(fpath):
    # check file extension
    fname = os.path.basename(fpath)
    fext = os.path.splitext(fname)[1].lower()
    frames = []
    if fext not in VALID_EXTS:
        exit(ERRORS["invalid_ext"])
    print('loading video...')
    data = cv.VideoCapture(fpath)
    for i in range(int(data.get(cv.CAP_PROP_FRAME_COUNT))):
        ret, frame = data.read()
        # if not ret:
        #     exit(ERRORS["video_read"])
        frames.append(frame)
    data.release()
    return frames

def get_font(fontpath, basesize):
    return imfont.truetype(fontpath, size=basesize, encoding='unic')

def crop_padding(arr):
    top, left = 0,0
    bot, right = arr.shape[0], arr.shape[1]
    for row in range(arr.shape[0]):
        if np.any(arr[row,:]):
            top = row
            break
    for row in range(arr.shape[0])[::-1]:
        if np.any(arr[row,:]):
            bot = row
            break
    for col in range(arr.shape[1]):
        if np.any(arr[:,col]):
            left = col
            break
    for col in range(arr.shape[1])[::-1]:
        if np.any(arr[:,col]):
            right = col
            break

    return arr[top:bot,left:right]

# NOTE: centered only works for grayscale
def render_char_img(char, font, size, gray=True, color=None, centered=False):
    width, height = font.getsize(char)
    offset = ((size-width)//2, (size-height))
    bg = 0 if gray else (0,0,0)
    cmode = 'L' if gray else 'RGB'
    fill = 255 if not color else color

    canvas = im.new(cmode, (size,size), color=bg)
    drawn = imdraw.Draw(canvas)
    drawn.text(offset, char, font=font, fill=fill)

    if centered:
        reshaped = crop_padding(np.array(canvas))
        c_off = ((size-reshaped.shape[0])//2, (size-reshaped.shape[1])//2)
        reshaped = np.pad(reshaped, ((c_off[0],),(c_off[1],)), mode='constant')

    return np.array(canvas)

def convert(frames, font, resize=True):
    frames_to_convert = tqdm(frames, desc='converting frames')
    new_frames = []
    for frame in frames_to_convert:
        #convert to grayscale
        image_raw = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        # resize
        image_tmp = cv.resize(image_raw, (RES_X,RES_Y)) if resize else image_raw
        # convert pixels to normalized ascii range
        image = normalize(image_tmp)

        canvas = np.zeros((RES_Y*CHAR_PIXEL_SIZE, RES_X*CHAR_PIXEL_SIZE))
        rows = []
        for y, row in enumerate(image):
            r = []
            for x, pixel in enumerate(row):
                char = render_char_img(ascii_map[pixel], font, CHAR_PIXEL_SIZE, centered=False)
                r.append(char)
            rows.append(r)
        
        new_frames.append(np.block(rows))
    return new_frames

if __name__ == '__main__':
    if len(sys.argv) < 2:
        exit("Must provide image path.")

    font = get_font(FONTS_PATH+FONT, CHAR_PIXEL_SIZE)
    data = load_file(sys.argv[1])
    out = convert(data, font)
    write_file(out, 'out0.mp4')