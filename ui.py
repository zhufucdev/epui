from enum import Enum
from threading import Thread
from time import sleep
from typing import *

from PIL import ImageDraw, Image, ImageFont

import resources
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

        self.__event_loop = Thread(target=self.__start_event_loop)

    def request_redraw(self):
        """
        Mark the current status as to invalidate
        """
        self.__requests += 1

    def __start_event_loop(self):
        self.__status = EventLoopStatus.RUNNING
        while self.__status == EventLoopStatus.RUNNING:
            current_requests = self.__requests
            if current_requests > 0:
                sleep(RELOAD_AWAIT)
                if current_requests == self.__requests:
                    self.__requests = 0
                    self.redraw_once()
                    if self.__redraw_listener:
                        self.__redraw_listener()

            sleep(RELOAD_INTERVAL)

    def redraw_once(self):
        self.__main_canvas.rectangle(
            [0, 0, self.canvas_size[0], self.canvas_size[1]], fill=255)  # clear canvas
        self.root_group.draw(self.__main_canvas, self.scale)

    def on_redraw(self, listener):
        self.__redraw_listener = listener

    def start(self):
        self.__event_loop.name = 'event_loop'
        self.__event_loop.start()
        self.__event_loop.join()

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
                 size: EffectiveSize = (ViewSize.WRAP_CONTENT, ViewSize.WRAP_CONTENT),
                 margin: Tuple[float, float, float, float] = (0, 0, 0, 0)) -> None:
        """
        :param margin: defined as [top, right, bottom, left]
        """
        self.position = position
        self.margin = margin
        self.size = size

    @staticmethod
    def default(position: Tuple[float, float] = (0, 0),
                size: EffectiveSize | float = ViewSize.WRAP_CONTENT,
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

        if size != ViewSize.WRAP_CONTENT:
            _size = size
        else:
            _size = (width, height)

        return ViewMeasurement(position, _size, _margin)


class View:
    """
    Something that can be drawn on the screen
    """

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
        place_holder = resources.get_image_tint('view-gallery', 0)
        size = self.actual_measurement.size

        def fit(rate):
            return place_holder.resize((int(place_holder.size[0] * rate), int(place_holder.size[1] * rate)))

        if size[0] > 64 and size[1] > 64:
            _size = (size[0] - 64 * scale, size[1] - 64 * scale)  # margin
        else:
            _size = size

        if not (_size[0] > place_holder.size[0] and _size[1] > place_holder.size[1]):
            if place_holder.size[0] > place_holder.size[1]:
                place_holder = fit(_size[0] / place_holder.size[0])
            else:
                place_holder = fit(_size[1] / place_holder.size[1])

        canvas._image.paste(place_holder,
                            util.int_vector(((size[0] - place_holder.size[0]) / 2,
                                             (size[1] - place_holder.size[1]) / 2)))
        canvas.rectangle(
            ((0, 0), (size[0], size[1])), fill=None, outline=0, width=6 * scale)


class Group(View):
    def __init__(self, context: Context, prefer: ViewMeasurement = ViewMeasurement.default()) -> None:
        self.__children = []
        super().__init__(context, prefer)

    def add_views(self, *children: View):
        self.__children.extend(children)
        self.context.request_redraw()

    def add_view(self, child: View):
        self.__children.append(child)
        self.context.request_redraw()

    def get_children(self):
        return [child for child in self.__children]

    def draw(self, canvas: ImageDraw.ImageDraw, scale: float):
        self.measure()
        for child in self.__children:
            partial = Image.new('L', util.int_vector(child.actual_measurement.size), 255)
            partial_canvas = ImageDraw.Draw(partial)
            child.draw(partial_canvas, scale)
            # TODO: decouple
            canvas._image.paste(partial, util.int_vector(child.actual_measurement.position))

    def content_size(self) -> Tuple[float, float]:
        _max = [0, 0]
        for child in self.__children:
            if child.content_size()[0] > _max[0]:
                _max[0] = child.content_size()[0]
            if child.content_size()[1] > _max[1]:
                _max[1] = child.content_size()[1]
        return _max[0], _max[1]

    def measure(self):
        for child in self.__children:
            position = child.preferred_measurement.position
            size = get_effective_size(child, self.actual_measurement.size)
            remaining_space = util.subtract(
                self.actual_measurement.size,
                child.preferred_measurement.position
            )
            if not util.is_positive(remaining_space):
                # there's no room for the child
                position = util.subtract(self.actual_measurement.size, size)
                if not util.is_positive(position):
                    position = (0, 0)
                    if size[0] > self.actual_measurement.size[0]:
                        size = (self.actual_measurement.size[0], child.size[1])
                    if size[1] > self.actual_measurement.size[1]:
                        size = (size[0], self.actual_measurement.size[1])

            elif not util.is_inside(remaining_space, size):
                # the child can not fit the group
                size = remaining_space

            child.actual_measurement = ViewMeasurement(position, size, child.preferred_measurement.margin)


class VGroup(Group):
    def __init__(self, context: Context,
                 alignment: ViewAlignmentHorizontal = ViewAlignmentHorizontal.LEFT,
                 prefer: ViewMeasurement = ViewMeasurement.default()) -> None:
        self.alignment = alignment
        super().__init__(context, prefer)

    def content_size(self) -> Tuple[float, float]:
        bound = [0, 0]
        for child in self.get_children():
            size = child.content_size()
            preference = child.preferred_measurement
            size = [size[0] + preference.margin[1] + preference.margin[3],
                    size[1] + preference.margin[0] + preference.margin[2]]
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

            if self.alignment == ViewAlignmentHorizontal.LEFT:
                position = (margin[3], margin[0] + last_measure_bottom)
            elif self.alignment == ViewAlignmentHorizontal.RIGHT:
                position = (self.actual_measurement.size[0] - size[0] - margin[3], margin[0] + last_measure_bottom)
            else:
                position = ((self.actual_measurement.size[0] - size[0]) / 2, margin[0] + last_measure_bottom)

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


class TextView(View):
    default_font = resources.get_file('DejaVuSans')

    def __init__(self, context: Context, text: str,
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
        return self.__text

    def set_text(self, text: str):
        if text != self.__text:
            self.__text = text
            self.context.request_redraw()

    def get_font(self):
        return self.__font

    def set_font(self, font: ImageFont.ImageFont):
        if font != self.__font:
            self.__font = font
            self.context.request_redraw()

    def get_font_size(self):
        return self.__font_size

    def set_font_size(self, font_size: float):
        if font_size != self.__font_size:
            self.__font_size = font_size
            self.context.request_redraw()

    def get_stroke(self):
        return self.__stroke

    def set_stroke(self, stroke: float):
        if stroke != self.__stroke:
            self.__stroke = stroke
            self.context.request_redraw()

    def get_fill_color(self):
        return self.__fill

    def set_fill_color(self, fill: int):
        if fill != self.__fill:
            self.__fill = fill
            self.context.request_redraw()

    def get_line_align(self):
        return self.__align

    def set_line_align(self, align: ViewAlignmentHorizontal):
        if align != self.__align:
            self.__align = align
            self.context.request_redraw()

    def get_align_vertical(self):
        return self.__align_vertical

    def set_align_vertical(self, align: ViewAlignmentVertical):
        if align != self.__align_vertical:
            self.__align_vertical = align
            self.context.request_redraw()

    def get_align_horizontal(self):
        return self.__align_horizontal

    def set_align_horizontal(self, align: ViewAlignmentHorizontal):
        if align != self.__align_horizontal:
            self.__align_horizontal = align
            self.context.request_redraw()

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
        for line in self.__text.splitlines():
            bound_box = single_line(line)
            max_width = max(max_width, bound_box[2])
            height += bound_box[3] + 5  # some fixed line margin

        return max_width, height

    def draw(self, canvas: ImageDraw.ImageDraw, scale: float):
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
            text=self.__text,
            font=self.__get_pil_font(),
            fill=self.__fill,
            stroke_width=self.__stroke * scale,
            align=self.__align.name.lower(),
        )
