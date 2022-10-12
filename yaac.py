# utils
import sys
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

# matrices and image processing
from PIL import Image as im
from PIL import ImageDraw as imdraw
from PIL import ImageFont as imfont
import cv2 as cv
import numpy as np

# UI
from tkinter import *
from tkinter import font, ttk, scrolledtext, filedialog
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
        self.steps = 0
        self.label = label
        self.frame_queue = Queue(maxsize=25)
        self.converted_queue = Queue(maxsize=25)

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

    def write_frames(self, output, properties):
        for _ in range(properties['framecount']):
            output.write(self.converted_queue.get())
            self.steps += 1

    def read_frames(self, data):
        for i in range(int(data.get(cv.CAP_PROP_FRAME_COUNT))):
            ret, frame = data.read()
            if not ret:
                raise ValueError(ERRORS["video_read"])
            self.frame_queue.put(frame)

    def convert_frames(self, properties, font, asciimap):
        charmap = self.preload_rasters(font, asciimap, properties['c_pixel_size'])
        c_res = (properties['c_res_y'], properties['c_res_x'])
        res = (properties['height'], properties['width'])

        for _ in range(properties['framecount']):
            frame = self.frame_queue.get()
            
            image_raw = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
            image_tmp = cv.resize(image_raw, c_res[::-1])
            image = normalize(image_tmp, asciimap)

            canvas = np.zeros(res)
            tmp = np.array([charmap[pixel] for row in image for pixel in row])
            canvas = np.vstack([np.hstack(tmp[i*c_res[1]:(i+1)*c_res[1]]) for i in range(c_res[0])])

            self.converted_queue.put(canvas)

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

    def run(self, inpath, outpath, fontpath, asciimap):
        if not inpath:
            return print("ERROR: no input path provided")
        if not outpath:
            return print("ERROR: no output path provided")
        if not fontpath:
            return print("ERROR: no font path provided")
        if len(asciimap) < 2:
            return print("ERROR: ASCII map has too few values")

        data = cv.VideoCapture(inpath)
        properties = {
            'fps': int(data.get(cv.CAP_PROP_FPS)),
            'width': int(data.get(cv.CAP_PROP_FRAME_WIDTH)),
            'height': int(data.get(cv.CAP_PROP_FRAME_HEIGHT)),
            'framecount': int(data.get(cv.CAP_PROP_FRAME_COUNT))
        }
        properties.update({
            'c_res_x': int(properties['width']*CHAR_SCALE),
            'c_res_y': int(properties['height']*CHAR_SCALE),
            'c_pixel_size': properties['width']//int(properties['width']*CHAR_SCALE)
        })
        fourcc = cv.VideoWriter_fourcc(*'mp4v')
        output = cv.VideoWriter(outpath, fourcc, properties['fps'], (properties['width'], properties['height']), False)

        self.label.configure(text="converting...")
        self.reset(properties['framecount'])

        loader, converter, writer = (
            threading.Thread(target=self.read_frames, args=(data,)),
            threading.Thread(target=self.convert_frames, args=(properties, self.get_font(fontpath, properties['c_pixel_size']), asciimap)),
            threading.Thread(target=self.write_frames, args=(output, properties))
        )
        loader.start()
        converter.start()
        writer.start()
        while writer.is_alive():
            self.update_pbar()

        data.release()
        output.release()
        loader.join()
        converter.join()
        writer.join()

        self.label.configure(text="done")
        self.pbar.step(-(properties['framecount']))
        self.reset()

    def reset(self, framecount=None):
        if framecount:
            self.pbar.configure(maximum=framecount)
        self.pbar['value'] = 0
        self.pbar.update()
        self.converted = []

    def update_pbar(self):
        self.pbar['value'] = self.steps
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
