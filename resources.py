import os

from PIL import Image

cached = {}

resources_dir = [f'{os.path.abspath(os.path.dirname(__file__))}/resources']
COLOR_TRANSPARENT = 254


def get_file(name: str):
    for path in resources_dir:
        for root, _, files in os.walk(path):
            for file in files:
                if file.startswith(name):
                    return os.path.join(root, file)
    return None


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
