import freetype

FONTS_PATH = '/usr/share/fonts/truetype/ubuntu/'
FONT = 'Ubuntu-M.ttf'

face = freetype.Face(FONTS_PATH + FONT)
face.set_char_size( 48*64 )
face.load_char('S')
bitmap = face.glyph.bitmap
print(type(bitmap))
print(type(bitmap.buffer))
print(bitmap.rows)
print(bitmap.width)
print(len(bitmap.buffer))