import logging
import numbers
from enum import Enum
from threading import Thread
from time import sleep
from typing import *

from PIL import ImageDraw, Image, ImageFont

import resources
from resources import COLOR_TRANSPARENT
import util

RELOAD_INTERVAL = 2
RELOAD_AWAIT = 1  # delay 1 second before each global invalidation


class EventLoopStatus(Enum):
    NOT_LOADED = 1
    RUNNING = 2
    STOPPED = 3


class Context:
    """
    A Context is shared between all its subviews to provide drawing functionality
    """

    def __init__(self, canvas: ImageDraw.ImageDraw, size: Tuple[float, float], scale: float = 1) -> None:
        self.__status = EventLoopStatus.NOT_LOADED
        self.root_group = Group(self)
        self.root_group.actual_measurement = ViewMeasurement((0, 0), size, (0, 0, 0, 0))
        self.__requests = 0
        self.__main_canvas = canvas
        self.canvas_size = size
        self.scale = scale
        self.__redraw_listener = None
        self.__panic_handler = None

        self.__event_loop = Thread(target=self.__start_event_loop)

    def request_redraw(self):
        """
        Mark the current status as to invalidate
        """
        self.__requests += 1

    def __start_event_loop(self):
        self.__status = EventLoopStatus.RUNNING
        while self.__status == EventLoopStatus.RUNNING:
            try:
                current_requests = self.__requests
                if current_requests > 0:
                    sleep(RELOAD_AWAIT)
                    if current_requests == self.__requests:
                        self.__requests = 0
                        self.redraw_once()
                        if self.__redraw_listener:
                            self.__redraw_listener()
                sleep(RELOAD_INTERVAL)
            except Exception as e:
                if self.__panic_handler:
                    self.__panic_handler(e)
                else:
                    raise e

    def redraw_once(self):
        self.__main_canvas.rectangle(
            [0, 0, self.canvas_size[0], self.canvas_size[1]], fill=255)  # clear canvas
        self.root_group.draw(self.__main_canvas, self.scale)

    def on_redraw(self, listener):
        self.__redraw_listener = listener

    def start(self):
        self.__event_loop.name = 'event_loop'
        self.__event_loop.start()

    def set_panic_handler(self, handler: Callable[[Exception], None]):
        self.__panic_handler = handler

    def destroy(self):
        """
        Mark the current status as stopped, and wait for the event loop to finish
        """
        if self.__status == EventLoopStatus.STOPPED:
            raise RuntimeError('Current context already stopped')

        self.__status = EventLoopStatus.STOPPED
        self.__event_loop.join()


class ViewSize(Enum):
    MATCH_PARENT = 1
    WRAP_CONTENT = 2


EffectiveSize = Tuple[ViewSize | float, ViewSize | float]


class ViewAlignmentVertical(Enum):
    TOP = 1
    CENTER = 2
    BOTTOM = 3


class ViewAlignmentHorizontal(Enum):
    LEFT = 1
    CENTER = 2
    RIGHT = 3


class ViewMeasurement:
    def __init__(self, position: Tuple[float, float] = (0, 0),
                 size: ViewSize | EffectiveSize = ViewSize.WRAP_CONTENT,
                 margin: Tuple[float, float, float, float] = (0, 0, 0, 0)) -> None:
        """
        :param margin: defined as [top, right, bottom, left]
        """
        self.position = position
        self.margin = margin
        self.size = size

    @staticmethod
    def default(position: Tuple[float, float] = (0, 0),
                size: ViewSize | EffectiveSize | float = ViewSize.WRAP_CONTENT,
                width: ViewSize | float = ViewSize.WRAP_CONTENT,
                height: ViewSize | float = ViewSize.WRAP_CONTENT,
                margin: float = 0,
                margin_top: float = 0,
                margin_right: float = 0,
                margin_bottom: float = 0,
                margin_left: float = 0) -> 'ViewMeasurement':
        if margin > 0:
            _margin = (margin, margin, margin, margin)
        else:
            _margin = (margin_top, margin_right, margin_bottom, margin_left)

        if size == ViewSize.MATCH_PARENT:
            _size = (size, size)
        elif type(size) is float or type(size) is tuple:
            _size = size
        else:
            _size = (width, height)

        return ViewMeasurement(position, _size, _margin)


class View:
    """
    Something that can be drawn on the screen

    By default, a plain View object draws nothing unless `View.draw_bounds_box` is overridden
    """
    draw_bounds_box = False

    def __init__(self, context: Context, prefer: ViewMeasurement = ViewMeasurement.default()) -> None:
        """
        Construct a view

        :param context: provides where the view lives in
        :param prefer: how the view prefers itself to be drawn,
         while the definitive right is under its parent's control
        """
        self.context = context
        self.preferred_measurement = prefer
        self.actual_measurement = prefer

    def invalidate(self):
        """
        This view is no longer valid and should be redrawn
        """
        self.context.request_redraw()

    def content_size(self) -> Tuple[float, float]:
        """
        Size of its bare content
        """
        return 64, 64

    def draw(self, canvas: ImageDraw.ImageDraw, scale: float):
        if View.draw_bounds_box:
            size = self.actual_measurement.size
            canvas.rectangle(((0, 0), (size[0], size[1])), fill=None, outline=0, width=int(2 * scale))


class Group(View):
    def __init__(self, context: Context, prefer: ViewMeasurement = ViewMeasurement.default()) -> None:
        self.__children: List[View] = []
        super().__init__(context, prefer)

    def add_views(self, *children: View):
        self.__children.extend(children)
        self.invalidate()

    def add_view(self, child: View):
        self.__children.append(child)
        self.invalidate()

    def get_children(self):
        return [child for child in self.__children]

    def clear(self):
        self.__children.clear()
        self.invalidate()

    def draw(self, canvas: ImageDraw.ImageDraw, scale: float):
        super().draw(canvas, scale)
        self.measure()
        if View.draw_bounds_box:
            canvas.rectangle(((0, 0), self.actual_measurement.size), outline=0, width=int(scale * 2))
        for child in self.__children:
            partial = Image.new('L', util.int_vector(child.actual_measurement.size), COLOR_TRANSPARENT)
            partial_canvas = ImageDraw.Draw(partial)
            child.draw(partial_canvas, scale)
            # TODO: decouple
            overlay(canvas._image, partial, util.int_vector(child.actual_measurement.position))

    def content_size(self) -> Tuple[float, float]:
        _max = [0, 0]
        for child in self.__children:
            margin = child.preferred_measurement.margin
            margin_h = margin[1] + margin[3]
            margin_v = margin[0] + margin[2]
            size = child.preferred_measurement.size
            if size[0] == ViewSize.WRAP_CONTENT \
                    and child.content_size()[0] + margin_h > _max[0]:
                _max[0] = child.content_size()[0] + margin_h
            elif type(size[0]) is float or type(size[0]) is int \
                    and size[0] + margin_h > _max[0]:
                _max[0] = size[0] + margin_h

            if size[1] == ViewSize.WRAP_CONTENT \
                    and child.content_size()[1] + margin_v > _max[1]:
                _max[1] = child.content_size()[1] + margin_v
            elif type(size[1]) is float or type(size[1]) is int \
                    and size[1] + margin_v > _max[1]:
                _max[1] = size[1] + margin_v
        return _max[0], _max[1]

    def measure(self):
        for child in self.__children:
            margin = child.preferred_measurement.margin
            position = util.plus(child.preferred_measurement.position, (margin[3], margin[0]))
            size = get_effective_size(child, self.actual_measurement.size)
            remaining_space = util.subtract(self.actual_measurement.size, position)
            if not util.is_positive(remaining_space):
                # there's no room for the child
                position = util.subtract(self.actual_measurement.size, util.plus(size, (margin[1], margin[2])))
                if not util.is_positive(position):
                    position = (margin[3], margin[0])
                    if size[0] > self.actual_measurement.size[0]:
                        size = (self.actual_measurement.size[0], size[1])
                    if size[1] > self.actual_measurement.size[1]:
                        size = (size[0], self.actual_measurement.size[1])

            elif not util.is_inside(remaining_space, size):
                # the child can not fit the group
                size = util.subtract(remaining_space, (margin[1], margin[2]))

            child.actual_measurement = ViewMeasurement(position, size, margin)


class VGroup(Group):
    def __init__(self, context: Context,
                 alignment: ViewAlignmentHorizontal = ViewAlignmentHorizontal.LEFT,
                 prefer: ViewMeasurement = ViewMeasurement.default()) -> None:
        self.__alignment = alignment
        super().__init__(context, prefer)

    def get_alignment(self):
        return self.__alignment

    def set_alignment(self, alignment: ViewAlignmentHorizontal):
        if self.__alignment != alignment:
            self.__alignment = alignment
            self.invalidate()

    def content_size(self) -> Tuple[float, float]:
        bound = [0, 0]
        for child in self.get_children():
            size = get_predefined_size(child)
            if size[0] > bound[0]:
                bound[0] = size[0]
            bound[1] += size[1]
        return bound[0], bound[1]

    def measure(self):
        measures = []

        for index, child in enumerate(self.get_children()):
            size = child.preferred_measurement.size
            margin = child.preferred_measurement.margin
            if type(size) is float:
                # percentage
                size = (self.actual_measurement.size[0], self.actual_measurement.size[1] * size)
            else:
                size = get_effective_size(child, self.actual_measurement.size)

            if index > 0:
                last = measures[index - 1]
                last_measure_bottom = last.position[1] + last.size[1] + last.margin[2]
            else:
                last_measure_bottom = 0

            if size[0] + margin[1] + margin[3] > self.actual_measurement.size[0]:
                size = (self.actual_measurement.size[0] - margin[1] - margin[3], size[1])
            if size[1] + margin[0] + margin[2] > self.actual_measurement.size[1] - last_measure_bottom:
                size = (size[0], self.actual_measurement.size[1] - last_measure_bottom - margin[0] - margin[2])

            if self.__alignment == ViewAlignmentHorizontal.LEFT:
                position = (margin[3], margin[0] + last_measure_bottom)
            elif self.__alignment == ViewAlignmentHorizontal.RIGHT:
                position = (self.actual_measurement.size[0] - size[0] - margin[3], margin[0] + last_measure_bottom)
            else:
                position = ((self.actual_measurement.size[0] - size[0]) / 2, margin[0] + last_measure_bottom)

            measurement = ViewMeasurement(position, size, margin)
            measures.append(measurement)
            child.actual_measurement = measurement


class HGroup(Group):
    def __init__(self, context: Context,
                 alignment: ViewAlignmentVertical = ViewAlignmentVertical.TOP,
                 prefer: ViewMeasurement = ViewMeasurement.default()) -> None:
        self.__alignment = alignment
        super().__init__(context, prefer)

    def get_alignment(self):
        return self.__alignment

    def set_alignment(self, alignment: ViewAlignmentVertical):
        if self.__alignment != alignment:
            self.__alignment = alignment
            self.invalidate()

    def content_size(self) -> Tuple[float, float]:
        bound = [0, 0]
        for child in self.get_children():
            size = get_predefined_size(child)
            if size[1] > bound[1]:
                bound[1] = size[1]
            bound[0] += size[0]
        return bound[0], bound[1]

    def measure(self):
        measures = []

        for index, child in enumerate(self.get_children()):
            size = child.preferred_measurement.size
            margin = child.preferred_measurement.margin
            if type(size) is float:
                # percentage
                size = (self.actual_measurement.size[0] * size, self.actual_measurement.size[1])
            else:
                size = get_effective_size(child, self.actual_measurement.size)

            if index > 0:
                last = measures[index - 1]
                last_measure_right = last.position[0] + last.size[0] + last.margin[1]
            else:
                last_measure_right = 0

            if size[0] + margin[1] + margin[3] > self.actual_measurement.size[0] - last_measure_right:
                size = (self.actual_measurement.size[0] - last_measure_right - margin[1] - margin[3], size[1])
            if size[1] + margin[0] + margin[2] > self.actual_measurement.size[1]:
                size = (size[0], self.actual_measurement.size[1] - margin[0] - margin[2])

            if self.__alignment == ViewAlignmentVertical.TOP:
                position = (margin[3] + last_measure_right, margin[0])
            elif self.__alignment == ViewAlignmentVertical.BOTTOM:
                position = (margin[3] + last_measure_right, self.actual_measurement.size[1] - size[1] - margin[2])
            else:
                position = (margin[3] + last_measure_right, (self.actual_measurement.size[1] - size[1]) / 2)

            measurement = ViewMeasurement(position, size, margin)
            measures.append(measurement)
            child.actual_measurement = measurement


def get_effective_size(child: View, parent_size: Tuple[float, float]):
    size = child.preferred_measurement.size
    if size[0] == ViewSize.MATCH_PARENT:
        size = (parent_size[0], size[1])
    elif size[0] == ViewSize.WRAP_CONTENT:
        size = (child.content_size()[0], size[1])
    if size[1] == ViewSize.MATCH_PARENT:
        size = (size[0], parent_size[1])
    elif size[1] == ViewSize.WRAP_CONTENT:
        size = (size[0], child.content_size()[1])
    return size


def get_predefined_size(child: View):
    size = child.content_size()
    preference = child.preferred_measurement
    # use preferred size if set numerically
    if isinstance(preference.size[0], numbers.Number):
        size = (preference.size[0], size[1])
    if isinstance(preference.size[1], numbers.Number):
        size = (size[0], preference.size[1])

    return (size[0] + preference.margin[1] + preference.margin[3],
            size[1] + preference.margin[0] + preference.margin[2])


def overlay(background: Image.Image, foreground: Image.Image, position: Tuple[int, int]):
    for y in range(foreground.size[1]):
        for x in range(foreground.size[0]):
            b_pos = (x + position[0], y + position[1])
            if not util.is_strictly_inside(background.size, b_pos):
                logging.warning('overlay: position out of bounds: %s', b_pos)
                break
            pf = foreground.getpixel((x, y))
            if pf != COLOR_TRANSPARENT:
                background.putpixel(b_pos, pf)


class TextView(View):
    default_font = resources.get_file('DejaVuSans')
    default_font_bold = resources.get_file('DejaVuSans-Bold')

    def __init__(self, context: Context, text: str | Callable[[], str],
                 font=default_font,
                 font_size: float = 10,
                 fill: int = 0,
                 stroke: float = 0,
                 line_align: ViewAlignmentHorizontal = ViewAlignmentHorizontal.LEFT,
                 align_horizontal: ViewAlignmentHorizontal = ViewAlignmentHorizontal.LEFT,
                 align_vertical: ViewAlignmentVertical = ViewAlignmentVertical.TOP,
                 prefer: ViewMeasurement = ViewMeasurement.default()):
        self.__text = text
        self.__font = font
        self.__font_size = font_size
        self.__fill = fill
        self.__align = line_align
        self.__align_horizontal = align_horizontal
        self.__align_vertical = align_vertical
        self.__stroke = stroke
        super().__init__(context, prefer)

    def get_text(self):
        return self.__text() if callable(self.__text) else self.__text

    def set_text(self, text: str | Callable[[], str]):
        if text != self.get_text():
            self.__text = text
            self.invalidate()

    def get_font(self):
        return self.__font

    def set_font(self, font: str):
        if font != self.__font:
            self.__font = font
            self.invalidate()

    def get_font_size(self):
        return self.__font_size

    def set_font_size(self, font_size: float):
        if font_size != self.__font_size:
            self.__font_size = font_size
            self.invalidate()

    def get_stroke(self):
        return self.__stroke

    def set_stroke(self, stroke: float):
        if stroke != self.__stroke:
            self.__stroke = stroke
            self.invalidate()

    def get_fill_color(self):
        return self.__fill

    def set_fill_color(self, fill: int):
        if fill != self.__fill:
            self.__fill = fill
            self.invalidate()

    def get_line_align(self):
        return self.__align

    def set_line_align(self, align: ViewAlignmentHorizontal):
        if align != self.__align:
            self.__align = align
            self.invalidate()

    def get_align_vertical(self):
        return self.__align_vertical

    def set_align_vertical(self, align: ViewAlignmentVertical):
        if align != self.__align_vertical:
            self.__align_vertical = align
            self.invalidate()

    def get_align_horizontal(self):
        return self.__align_horizontal

    def set_align_horizontal(self, align: ViewAlignmentHorizontal):
        if align != self.__align_horizontal:
            self.__align_horizontal = align
            self.invalidate()

    def __get_pil_font(self):
        return ImageFont.truetype(font=self.__font, size=self.__font_size)

    def content_size(self) -> Tuple[float, float]:
        def single_line(text: str):
            return self.__get_pil_font().getbbox(
                text=text,
                stroke_width=self.__stroke,
            )

        max_width = 0
        height = 0
        for line in self.get_text().splitlines():
            bound_box = single_line(line)
            max_width = max(max_width, bound_box[2])
            height += bound_box[3] + 5  # some fixed line margin

        return max_width, height

    def draw(self, canvas: ImageDraw.ImageDraw, scale: float):
        super().draw(canvas, scale)
        content_size = self.content_size()
        if self.__align_vertical == ViewAlignmentVertical.TOP:
            y = 0
        elif self.__align_vertical == ViewAlignmentVertical.BOTTOM:
            y = self.actual_measurement.size[1] - content_size[1]
        else:
            y = (self.actual_measurement.size[1] - content_size[1]) / 2

        if self.__align_horizontal == ViewAlignmentHorizontal.LEFT:
            x = 0
        elif self.__align_horizontal == ViewAlignmentHorizontal.RIGHT:
            x = self.actual_measurement.size[0] - content_size[0]
        else:
            x = (self.actual_measurement.size[0] - content_size[0]) / 2

        canvas.text(
            xy=(x, y),
            text=self.get_text(),
            font=self.__get_pil_font(),
            fill=self.__fill,
            stroke_width=self.__stroke * scale,
            align=self.__align.name.lower(),
        )


class Surface(View):
    """
    Surface is a view that displays pure color
    """

    def __init__(self, context: Context, radius: int = 0, fill: int = 0, stroke: int = COLOR_TRANSPARENT,
                 stroke_width: int = 1, prefer: ViewMeasurement = ViewMeasurement.default()):
        self.__fill = fill
        self.__stroke = stroke
        self.__width = stroke_width
        self.__radius = radius
        super().__init__(context, prefer)

    def content_size(self) -> Tuple[float, float]:
        def effective(size: EffectiveSize | float):
            if type(size) is ViewSize:
                return 0
            else:
                return size

        prefer = self.preferred_measurement.size
        if type(prefer) is tuple:
            return effective(prefer[0]), effective(prefer[1])
        else:
            return 64, 64

    def get_fill(self):
        return self.__fill

    def set_fill(self, fill: int):
        if fill != self.__fill:
            self.__fill = fill
            self.invalidate()

    def get_stroke(self):
        return self.__stroke

    def set_stroke(self, stroke: int):
        if self.__stroke != stroke:
            self.__stroke = stroke
            self.invalidate()

    def get_radius(self):
        return self.__radius

    def set_radius(self, radius):
        if self.__radius != radius:
            self.__radius = radius
            self.invalidate()

    def get_stroke_width(self):
        return self.__width

    def set_stroke_width(self, width: int):
        if self.__width != width:
            self.__width = width
            self.invalidate()

    def draw(self, canvas: ImageDraw.ImageDraw, scale: float):
        super().draw(canvas, scale)
        if self.__stroke != COLOR_TRANSPARENT:
            outline = self.__stroke
        else:
            outline = None

        if self.__fill != COLOR_TRANSPARENT and self.__width > 0:
            fill = self.__fill
            width = self.__width
        else:
            fill = None
            width = 0

        size = (self.actual_measurement.size[0] - width, self.actual_measurement.size[1] - width)

        canvas.rounded_rectangle(
            xy=((0, 0), size),
            radius=self.__radius * scale,
            fill=fill,
            outline=outline,
            width=self.__width
        )


class ImageContentFit(Enum):
    """
    Stretch the image to its largest, no space left
    """
    STRETCH = 0
    """
    Crop the image to fit the view, no space left
    """
    CROP = 1
    """
    Fit the image to view's height or width, space left
    """
    FIT = 2


class ImageView(View):
    """
    A view that shows a static view of image
    """

    def __init__(self, context: Context, image: Image.Image | str,
                 fit: ImageContentFit = ImageContentFit.FIT,
                 prefer: ViewMeasurement = ViewMeasurement.default()):
        """
        Create a ImageView
        :param context: the context
        :param fit: method to handle oversized images or something
        :param image: the image instance or its representation
        :param prefer: the preferred measurement
        """
        super().__init__(context, prefer)
        self.__image = image
        self.__fit = fit

    def get_image(self):
        return self.__image

    def set_image(self, image: Image.Image | str):
        if image != self.__image:
            self.__image = image
            self.invalidate()

    def get_fit(self):
        return self.__fit

    def set_fit(self, fit: ImageContentFit):
        if fit != self.__fit:
            self.__fit = fit
            self.invalidate()

    def content_size(self) -> Tuple[float, float]:
        return self.__image.size

    def draw(self, canvas: ImageDraw.ImageDraw, scale: float):
        super().draw(canvas, scale)

        if self.actual_measurement.size == self.content_size():
            overlay(canvas._image, self.__image, (0, 0))
            return

        if self.__fit == ImageContentFit.STRETCH:
            resized = self.__image.resize(self.actual_measurement.size)
            overlay(canvas._image, resized, (0, 0))
        elif self.__fit == ImageContentFit.CROP:
            content_size = self.content_size()
            target_size = self.actual_measurement.size
            if content_size[0] > content_size[1]:
                rate = target_size[1] / content_size[1]
                left = int((content_size[0] * rate + target_size[0]) / 2)
                resized = self.__image.resize(
                    (int(content_size[0] * rate), target_size[1])
                )
                overlay(canvas._image, resized, (-left, 0))
            else:
                rate = target_size[0] / content_size[0]
                top = int((content_size[1] * rate + target_size[1]) / 2)
                resized = self.__image.resize(
                    (target_size[0], int(content_size[1] * rate))
                )
                overlay(canvas._image, resized, (-top, 0))
        else:
            content_size = self.content_size()
            target_size = self.actual_measurement.size
            if content_size[0] > content_size[1]:
                rate = target_size[0] / content_size[0]
                top = int((target_size[1] - content_size[1] * rate) / 2)
                resized = self.__image.resize(
                    (target_size[0], int(content_size[1] * rate))
                )
                overlay(canvas._image, resized, (0, top))
            else:
                rate = target_size[1] / content_size[1]
                left = int((target_size[0] - content_size[0] * rate) / 2)
                resized = self.__image.resize(
                    (int(content_size[0] * rate), target_size[1])
                )
                overlay(canvas._image, resized, (left, 0))
