import sys
from PIL import Image, ImageOps
import numpy as np

MAXWIDTH = 80 # number of characters per line
STYLEBIAS = 2.5 # adjust aspect ratio based on font and line formatting (terminal-dependent)
ascii_map = " .^,:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$" # revised from https://stackoverflow.com/a/66140774 without escape-chars
normalize = lambda x: ((x/255)*(len(ascii_map)-1)).astype(int)
resize = lambda y: y.resize((MAXWIDTH,round(MAXWIDTH/(STYLEBIAS*(y.size[0]/y.size[1])))))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        exit("Must provide image path.")

    image_raw = ImageOps.grayscale(Image.open(sys.argv[1]))
    image = normalize(np.asarray(resize(image_raw)))

    out = '\n'
    for row in image:
        text = [ascii_map[i] for i in row]
        out += ''.join(map(str, text)) + '\n'

    print(out)