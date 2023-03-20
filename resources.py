from PIL import Image
import os

cached = {}

def get(name: str) -> Image.Image:
    if name in cached:
        return cached[name]
    else:
        candidates = (f for f in os.listdir('./resources') if f.startswith(name))
        res = Image.open(f'./resources/{next(candidates)}')
        cached[name] = res
        return res
    
