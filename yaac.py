from multiprocessing.pool import ThreadPool
import sys
import os
from tkinter import filedialog
from PIL import Image as im
from PIL import ImageDraw as imdraw
from PIL import ImageFont as imfont
import cv2 as cv
import numpy as np

from tkinter import *
from tkinter import font, ttk, scrolledtext
from matplotlib import font_manager
from concurrent.futures import ThreadPoolExecutor, process

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

PATH = '/home/n8/Videos'
CHAR_SCALE = 0.1
BAR_DELTA = 100

# https://docs.opencv.org/3.4/d4/d15/group__videoio__flags__base.html#gaeb8dd9c89c10a5c63c139bf7c4f5704d

ascii_map = " .^,:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$" # revised from https://stackoverflow.com/a/66140774 without escape-chars
normalize = lambda x, amap: ((x/255)*(len(amap)-1)).astype(np.uint8)
scaled = lambda x: round(x*SCALE)
round_to_multiple = lambda m,n: m*round(n/m)

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
        self.path = None

    def browse(self):
        name = self.opencontext(
            title=self.title, 
            filetypes=self.types,
            initialdir='.' if not PATH else PATH
        )
        self.dialog.configure(text=name)
        self.path = name

class AsciiMenu:
    def __init__(self, menu, label):
        self.menu = menu
        self.label = label
        self.map = self.menu.get()

    def update_map(self):
        self.map = self.menu.get()

class Converter:
    def __init__(self, button, pbar, label):
        self.button = button
        self.pbar = pbar
        self.label = label

    def get_font(self, path, basesize):
        return imfont.truetype(path, size=basesize, encoding='unic')

    def preload_rasters(self, font, asciimap, size):
        '''
        desc: for each glyph in a font, create a raster for it
        params:
            font = font class from file
            size = char pixel size
        return: array of char rasters
        '''

        return np.array([self.rasterize_char(char, font, size) for char in asciimap])

    def write_file(self, frames, fname, properties):
        '''
        desc: write frames to video
        params:
            frames = list of arrays containing frames of video
            fname = output file name (ext included)
            properties = video metadata
        return: none (outfile written to fs)
        '''

        self.label.configure(text="writing to file...")

        res = (properties['width'], properties['height'])
        fourcc = cv.VideoWriter_fourcc(*'mp4v')
        output = cv.VideoWriter(fname, fourcc, properties['fps'], res, False)

        for i, frame in enumerate(frames):
            output.write(frame)
            if i%BAR_DELTA == 0:
                self.pbar.step(BAR_DELTA)
                self.pbar.update()
        output.release()

    def load_file(self, fpath):
        '''
        desc: load video file
        params:
            fpath = absolute path to video file
        return: array of (raw) frames from video
        '''

        fname = os.path.basename(fpath)
        fext = os.path.splitext(fname)[1].lower()
        frames = []

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

    def rasterize_char(self, char, font, size, color=None):
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

    def convert(self, frames, properties, font, asciimap, resize=True):
        '''
        desc: convert frames to ascii-fied version using a given font
        params:
            frames = array of raw video frames
            properties = video metadata
            font = font class from file
            resize = whether conversion is done on downscaled version of frames or raw frames' pixels
        return: list of converted frame arrays
        '''

        self.label.configure(text="converting...")

        new_frames = []
        charmap = self.preload_rasters(font, asciimap, properties['c_pixel_size'])
        c_res = (properties['c_res_y'], properties['c_res_x'])
        res = (properties['height'], properties['width'])

        for i, frame in enumerate(frames):
            image_raw = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
            image_tmp = cv.resize(image_raw, c_res[::-1]) if resize else image_raw
            image = normalize(image_tmp, asciimap)

            canvas = np.zeros(res)
            tmp = np.array([charmap[pixel] for row in image for pixel in row])
            canvas = np.vstack([np.hstack(tmp[i*c_res[1]:(i+1)*c_res[1]]) for i in range(c_res[0])])

            new_frames.append(canvas)
            if i%BAR_DELTA == 0:
                self.pbar.step(BAR_DELTA)
                self.pbar.update()

        return new_frames

    def run(self, inpath, outpath, fontpath, asciimap):
        if not inpath:
            return print("ERROR: no input path provided")
        if not outpath:
            return print("ERROR: no output path provided")
        if not fontpath:
            return print("ERROR: no font path provided")
        if len(asciimap) < 2:
            return print("ERROR: ASCII map has too few values")

        frames, properties = self.load_file(inpath) 
        self.reset_pbar(frames)
        font = self.get_font(fontpath, properties['c_pixel_size']) 
        out = self.convert(frames, properties, font, asciimap)
        self.write_file(out, outpath, properties) 
        self.label.configure(text="done")

    def reset_pbar(self, frames):
        self.pbar['value'] = 0
        self.pbar.configure(maximum=round_to_multiple(BAR_DELTA, 2*len(frames)+BAR_DELTA))
        self.pbar.update()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        PATH = sys.argv[1]

    root = Tk()
    style = load_style()
    SCALE = root.winfo_fpixels('1i')/BASE_DPI
    rootFont = font.Font(family='TkDefaultFont', size=18)
    elementFont = font.Font(family='TkDefaultFont', size=14)

    # ROOT PROPERTIES
    root.title('YAAC')
    root.pack_propagate(0)
    root.focus()
    root.geometry(str(scaled(700)) + "x" + str(scaled(200)+7) + "+" + str(-7) + "+" + str(0))
    root.rowconfigure(1, weight=1)
    root.columnconfigure(1, weight=1)
    root.resizable(False, False)

    # FONT MENU
    fontFamilies = sorted(list(font.families()))
    fontMenuVar = StringVar(root)
    fontMenuVar.set(font.nametofont("TkDefaultFont").actual()['family'])
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
    inputDialogText = Label(root, background='white', text="", height=1, width=50, font=elementFont)
    inputDialogButton = Button(root, text="<- load file")
    inputDialog = FileExplorer(inputDialogText, inputDialogButton, isInput=True)

    outputDialogText = Label(root, background='white', text="", height=1, width=50, font=elementFont)
    outputDialogButton = Button(root, text="<- save as")    
    outputDialog = FileExplorer(outputDialogText, outputDialogButton, isInput=False)

    # ASCII SETTINGS
    asciiMenuEntryVar = StringVar(root)
    asciiMenuEntryVar.set(ascii_map)
    asciiMenuLabel = Label(root, text="ASCII range", font=rootFont)
    asciiMenuEntry = Entry(root, text=asciiMenuEntryVar)
    asciiMenu = AsciiMenu(asciiMenuEntry, asciiMenuLabel)

    # ACTION
    actionMenuButton = Button(root, background='green', foreground='white', text='START')
    actionMenuPBar = ttk.Progressbar(root, orient='horizontal')
    actionMenuLabel = Label(root, text="", font=elementFont)
    actionMenu = Converter(actionMenuButton, actionMenuPBar, actionMenuLabel)

    # CONSOLE LOG
    consoleBox = scrolledtext.ScrolledText(root, height=4, font=elementFont)
    consoleBoxLabel = Label(root, text="Log", font=rootFont)
    log = Console(consoleBox, consoleBoxLabel)
    sys.stdout = log

    # LAYOUT
    inputDialog.dialog.grid(row=0, column=0, sticky='new')
    inputDialog.button.grid(row=0, column=1, sticky='nw')
    outputDialog.dialog.grid(row=1, column=0, sticky='new')
    outputDialog.button.grid(row=1, column=1, sticky='nw')
    fontMenu.label.grid(row=0, column=2, sticky='ne')
    fontMenu.menu.grid(row=1, column=2, sticky='ne')
    asciiMenu.label.grid(row=2, column=0, sticky='w')
    asciiMenu.menu.grid(row=3, column=0, columnspan=2, sticky='ew')
    actionMenu.button.grid(row=3, column=2, sticky='e')
    actionMenu.pbar.grid(row=4, column=0, columnspan=2, sticky='ew')
    actionMenu.label.grid(row=4, column=2, sticky='w')
    log.label.grid(row=5, column=0, sticky='sw')
    log.textbox.grid(row=6, column=0, columnspan=3, sticky='s')

    fontMenu.menu.bind("<<ComboboxSelected>>", lambda _: fontMenu.assign_font())
    inputDialog.button.configure(command=inputDialog.browse)
    outputDialog.button.configure(command=outputDialog.browse)
    asciiMenu.menu.bind("<FocusOut>", lambda _: asciiMenu.update_map())
    actionMenu.button.configure(command=lambda: actionMenu.run(inputDialog.path, outputDialog.path, fontMenu.path, asciiMenu.map))

    root.mainloop()
