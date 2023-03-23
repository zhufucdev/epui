import os

from PIL import Image

cached = {}

RESOURCES_DIR = f'{os.path.abspath(os.path.dirname(__file__))}/resources'
COLOR_TRANSPARENT = 254


def get_file(name: str):
    candidates = (os.path.join(RESOURCES_DIR, f) for f in os.listdir(RESOURCES_DIR) if f.startswith(name))
    return next(candidates)


def get_image(name: str) -> Image.Image:
    if name in cached:
        return cached[name]
    else:
        res = Image.open(get_file(name))
        background = Image.new(mode='L', size=res.size, color=COLOR_TRANSPARENT)
        background.paste(res, mask=res)
        cached[name] = background
        return background


def get_image_tint(name: str, grayscale: int) -> Image.Image:
    res = get_image(name)
    for y in range(res.size[1]):
        for x in range(res.size[0]):
            current = res.getpixel((x, y))
            if current < 255 and current != COLOR_TRANSPARENT:
                res.putpixel((x, y), grayscale)
    return res
