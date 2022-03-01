# import freetype
from tkinter import *
from tkinter import ttk
import numpy as np
from PIL import Image as im
from PIL import ImageTk as imtk
from PIL import ImageFont as imfont
from PIL import ImageDraw as draw
from itertools import chain

FONTS_PATH = '/usr/share/fonts/truetype/ubuntu/'
FONT = 'Ubuntu-M.ttf'

WIDTH = 200
HEIGHT = 200

SIZE = 100

gui = Tk()

char = '_'

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
    drawn = draw.Draw(canvas)
    drawn.text(offset, char, font=font, fill=fill)

    if centered:
        reshaped = crop_padding(np.array(canvas))
        c_off = ((size-reshaped.shape[0])//2, (size-reshaped.shape[1])//2)
        reshaped = np.pad(reshaped, ((c_off[0],),(c_off[1],)), mode='constant')
        canvas = im.fromarray(reshaped)

    return imtk.PhotoImage(canvas)

font = get_font(FONTS_PATH+FONT, SIZE)
img = render_char_img(char, font, SIZE, centered=False)

# GUI for testing
gui.geometry("%sx%s" % (WIDTH, HEIGHT))
label = Label(gui, image=img)
label.grid()
gui.mainloop()