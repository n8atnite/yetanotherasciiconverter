import sys
import os
from tkinter import filedialog
from PIL import Image as im
from PIL import ImageDraw as imdraw
from PIL import ImageFont as imfont
import cv2 as cv
import numpy as np
from tqdm import tqdm
import argparse

from tkinter import *
from tkinter import font, ttk, scrolledtext
from matplotlib import font_manager

BASE_DPI = 72
SCALE = 1

ERRORS = {
    "invalid_ext": "Not a valid file extension.",
    "invalid_in": "Not a valid input file path.",
    "invalid_out": "Not a valid output file path.",
    "invalid_font": "Could not find font from path.",
    "missing_path": "Must provide video path.",
    "video_read": "Cannot read frame from video stream."
}

OUTNAME = 'out.mp4'
FONTS_PATH = '/usr/share/fonts/truetype/ubuntu/'
FONT = 'Ubuntu-M.ttf'
VALID_EXTS = ('.mp4', '.m4v', '.avi')
CHAR_SCALE = 0.1

# https://docs.opencv.org/3.4/d4/d15/group__videoio__flags__base.html#gaeb8dd9c89c10a5c63c139bf7c4f5704d

ascii_map = " .^,:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$" # revised from https://stackoverflow.com/a/66140774 without escape-chars
normalize = lambda x: ((x/255)*(len(ascii_map)-1)).astype(np.uint8)
scaled = lambda x: round(x*SCALE)

def get_font(fontpath, basesize):
    return imfont.truetype(fontpath, size=basesize, encoding='unic')

def preload_rasters(font, size):
    '''
    desc: for each glyph in a font, create a raster for it
    params:
        font = font class from file
        size = char pixel size
    return: array of char rasters
    '''

    return np.array([rasterize_char(char, font, size) for char in ascii_map])

def write_file(frames, fname, properties):
    '''
    desc: write frames to video
    params:
        frames = list of arrays containing frames of video
        fname = output file name (ext included)
        properties = video metadata
    return: none (outfile written to fs)
    '''

    res = (properties['width'], properties['height'])
    fourcc = cv.VideoWriter_fourcc(*'mp4v')
    output = cv.VideoWriter(fname, fourcc, properties['fps'], res, False)
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

    left, top, right, bottom = font.getbbox(char)
    width, height = (right-left), (bottom-top)
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
    charmap = preload_rasters(font, properties['c_pixel_size'])
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

def load_style():
    style = ttk.Style()
    style_settings = (
        ('TCombobox', {
            'width': scaled(30),
            'arrowsize': scaled(30),
            # 'postoffset': (0, 0, 100, 0)
        }),
        ('Vertical.TScrollbar', {
            'width': scaled(30),
            'arrowsize': scaled(30)
        }),
    )
    for setting in style_settings:
        style.configure(setting[0], **setting[1])

    return style

class Console:
    def __init__(self, textbox, label):
        self.textbox = textbox
        self.label = label

    def write(self, text):
        self.textbox.insert(END, text)

    def flush(self):
        pass

class FontMenu:
    def __init__(self, menu, label):
        self.menu = menu
        self.label = label
        self.path = self.find_fontpath_from_props(font.Font(font=self.menu['font']).actual())
    
    def assign_font(self):
        self.menu.configure(font=font.Font(family=self.menu.get(), size=14)),
        self.path = self.find_fontpath_from_props(font.Font(font=self.menu['font']).actual())

    def find_fontpath_from_props(self, props):
        accepted = ('family', 'slant', 'size', 'weight')
        filtered = {}
        for key, value in props.items():
            if key in accepted:
                if key == 'slant':
                    if value == 'roman':
                        filtered['style'] = 'normal'
                    else:
                        filtered['style'] = value
                else:
                    filtered[key] = value
        new_props = font_manager.FontProperties(**filtered)
        try:
            path = font_manager.findfont(new_props, fallback_to_default=False)
        except ValueError:
            print("ERROR: font path not found for %s" % props['family'])
            return None
        return path

class FileExplorer:
    def __init__(self, dialog, button, isInput=True):
        self.dialog = dialog
        self.button = button
        self.opencontext = filedialog.askopenfilename if isInput else filedialog.asksaveasfilename
        self.title = "LOAD FILE" if isInput else "SAVE FILE"
        self.types = (
            ("mp4", "*.mp4"), 
            ("matroska", "*.mkv"), 
            ("avi", "*.avi")
        ) if isInput else (("mp4", "*.mp4"),)
        self.filename = ''

    def browse(self):
        name = self.opencontext(
            title=self.title, 
            filetypes=self.types
        )
        self.dialog.configure(text=name)

if __name__ == '__main__':
    # parser = argparse.ArgumentParser(description='''
    #  __    __  ______  ______  ____      
    # /\ \  /\ \/\  _  \/\  _  \/\  _`\    
    # \ `\`\\\/'/\ \ \L\ \ \ \L\ \ \ \/\_\  
    #  `\ `\ /'  \ \  __ \ \  __ \ \ \/_/_ 
    #    `\ \ \   \ \ \/\ \ \ \/\ \ \ \L\ \\
    #      \ \_\   \ \_\ \_\ \_\ \_\ \____/
    #       \/_/    \/_/\/_/\/_/\/_/\/___/ 
                                        
    # Yet Another Ascii Converter by n8atnite
    # convert .mp4 or .avi to asciified .mp4
    # ''', formatter_class=argparse.RawTextHelpFormatter)
    # parser.add_argument('-t', '--fontpath', default=FONTS_PATH+FONT, help='font/typeface filepath (.ttf)')
    # parser.add_argument('inpath', help='full video file path (including name and ext)')
    # parser.add_argument('-o', '--outpath', default='ascii.mp4', help='output video path (including name and .mp4/.mkv ext)')
    # args = parser.parse_args()

    # if not os.path.exists(args.inpath):
    #     raise FileNotFoundError(ERRORS["invalid_in"])
    # if not os.path.exists(os.path.split(os.path.abspath(args.outpath))[0]):
    #     raise FileNotFoundError(ERRORS["invalid_out"])
    # if not os.path.exists(args.fontpath):
    #     raise FileNotFoundError(ERRORS["invalid_font"])

    root = Tk()
    style = load_style()
    SCALE = root.winfo_fpixels('1i')/BASE_DPI
    rootFont = font.Font(family='TkDefaultFont', size=18)
    elementFont = font.Font(family='TkDefaultFont', size=14)

    # ROOT PROPERTIES
    root.title('YAAC')
    root.pack_propagate(0)
    root.focus()
    root.geometry(str(scaled(800)) + "x" + str(scaled(600)+7) + "+" + str(-7) + "+" + str(0))

    # FONT MENU
    fontFamilies = sorted(list(font.families()))
    fontMenuVar = StringVar(root)
    fontMenuVar.set(fontFamilies[0])
    fontMenuBox = ttk.Combobox(
        root, 
        textvariable=fontMenuVar, 
        values=fontFamilies, 
        font=elementFont, 
        style='font.TCombobox',
    )
    fontMenuLabel = Label(root, text="Font", font=rootFont)
    fontMenu = FontMenu(fontMenuBox, fontMenuLabel)

    # FILE IO
    inputDialogText = Label(root, background='white', text="", height=1, font=elementFont)
    inputDialogButton = Button(root, text="<- load file")
    inputDialog = FileExplorer(inputDialogText, inputDialogButton, isInput=True)

    outputDialogText = Label(root, background='white', text="", height=1, font=elementFont)
    outputDialogButton = Button(root, text="<- save as")    
    outputDialog = FileExplorer(outputDialogText, outputDialogButton, isInput=False)

    # CONSOLE LOG
    consoleBox = scrolledtext.ScrolledText(root, height=4, font=elementFont)
    consoleBoxLabel = Label(root, text="Log", font=rootFont)
    log = Console(consoleBox, consoleBoxLabel)
    sys.stdout = log

    # LAYOUT
    inputDialog.dialog.grid(row=0, column=0, sticky='ew')
    inputDialog.button.grid(row=0, column=1, sticky='w')
    outputDialog.dialog.grid(row=1, column=0, sticky='ew')
    outputDialog.button.grid(row=1, column=1, sticky='w')
    fontMenu.label.grid(row=0, column=2, sticky='ne')
    fontMenu.menu.grid(row=1, column=2, sticky='ne')
    log.label.grid(row=3, column=0, sticky='sw')
    log.textbox.grid(row=4, column=0, columnspan=3, sticky='s')

    fontMenu.menu.bind("<<ComboboxSelected>>", lambda _: fontMenu.assign_font())
    inputDialog.button.configure(command=inputDialog.browse)
    outputDialog.button.configure(command=outputDialog.browse)

    # frames, properties = load_file(args.inpath) -> inputDialog.filename
    # font = get_font(args.fontpath, properties['c_pixel_size']) -> fontMenu.path,
    # out = convert(frames, properties, font)
    # write_file(out, args.outpath, properties) -> outputDialog.filename

    root.mainloop()
