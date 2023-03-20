from enum import Enum
from threading import Thread
from time import sleep
from typing import *

from PIL import ImageDraw, Image

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
        self.root_group.draw(
            self.__main_canvas, self.scale)

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
                width: ViewSize | float = ViewSize.WRAP_CONTENT,
                height: ViewSize | float = ViewSize.WRAP_CONTENT,
                margin_top: float = 0,
                margin_right: float = 0,
                margin_bottom: float = 0,
                margin_left: float = 0) -> 'ViewMeasurement':
        return ViewMeasurement(position, (width, height), (margin_top, margin_right, margin_bottom, margin_left))


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
        place_holder = resources.get_tint('view-gallery', 125)
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
        measurements = self.measure()
        for child in self.__children:
            child.actual_measurement = measurements[child]
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

    def measure(self) -> Dict[View, ViewMeasurement]:
        measurements = {}
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
            measurements[child] = ViewMeasurement(position, size, child.preferred_measurement.margin)

        return measurements


class VGroup(Group):
    def __init__(self, context: Context,
                 alignment: ViewAlignmentHorizontal = ViewAlignmentHorizontal.LEFT,
                 prefer: ViewMeasurement = ViewMeasurement.default()) -> None:
        self.alignment = alignment
        super().__init__(context, prefer)

    def measure(self) -> Dict[View, ViewMeasurement]:
        measurements = {}
        measurements_indexed = []

        for index, child in enumerate(super().get_children()):
            position = child.preferred_measurement.position
            size = child.preferred_measurement.size
            margin = child.preferred_measurement.margin
            if type(size) is float:
                # percentage
                size = (self.actual_measurement.size[0], self.actual_measurement.size[1] * size)
            else:
                size = get_effective_size(child, self.actual_measurement.size)

            if index > 0:
                last = measurements_indexed[index - 1]
                last_measure_bottom = last.position[1] + last.size[1] + last.margin[2]
            else:
                last_measure_bottom = 0

            if size[0] + margin[1] + margin[3] > self.actual_measurement.size[0]:
                size = (
                    self.actual_measurement.size[0] - margin[1] - margin[3], size[1])

            if self.alignment == ViewAlignmentHorizontal.LEFT:
                position = (margin[3], margin[0] + last_measure_bottom)
            elif self.alignment == ViewAlignmentHorizontal.RIGHT:
                position = (self.actual_measurement.size[0] - size[0], margin[0] + last_measure_bottom)
            elif self.alignment == ViewAlignmentHorizontal.CENTER:
                position = ((self.actual_measurement.size[0] - size[0]) / 2, margin[0] + last_measure_bottom)

            measurements[child] = ViewMeasurement(position, size, margin)
            measurements_indexed.append(ViewMeasurement(position, size, margin))

        return measurements


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
