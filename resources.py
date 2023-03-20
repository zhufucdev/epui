from PIL import Image, ImageFilter
import os

cached = {}


def get(name: str) -> Image.Image:
    if name in cached:
        return cached[name]
    else:
        candidates = (f for f in os.listdir('./resources') if f.startswith(name))
        res = Image.open(f'./resources/{next(candidates)}')
        background = Image.new(mode='L', size=res.size, color=255)
        background.paste(res, mask=res)
        cached[name] = background
        return background


def get_tint(name: str, grayscale: int) -> Image.Image:
    res = get(name)
    for y in range(res.size[1]):
        for x in range(res.size[0]):
            if res.getpixel((x, y)) < 255:
                res.putpixel((x, y), grayscale)
    return res
