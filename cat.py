from PIL import Image
from ui import Context, ImageView, ViewMeasurement
import resources
import random


class RandomCatView(ImageView):
    def __init__(self, context: Context, prefer: ViewMeasurement = ViewMeasurement.default(width=256, height=256)):
        self.__image = self.__get_random_cat()
        super().__init__(context=context, image=self.__image, prefer=prefer)

    @staticmethod
    def __get_random_cat() -> Image.Image:
        num = random.randint(0, 29)
        f = resources.get_file(f'cat_sticker_{num}')
        return Image.open(f)
