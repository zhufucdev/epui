from PIL import ImageDraw, Image
from typing import *
from time import sleep
from threading import Thread
from enum import Enum

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
    current_requests = self.__requests
    self.root_group.actual_measurement = ViewMeasurement((0, 0), self.canvas_size, (0, 0, 0, 0))
    while self.__status == EventLoopStatus.RUNNING:
      current_requests = self.__requests
      if current_requests > 0:
        sleep(RELOAD_AWAIT)
        if current_requests == self.__requests:
          self.__requests = 0
          self.__main_canvas.rectangle(
              [0, 0, self.canvas_size[0], self.canvas_size[1]], fill=255)  # clear canvas
          self.root_group.draw(
              self.__main_canvas, self.scale)
          if self.__redraw_listener:
            self.__redraw_listener()

      sleep(RELOAD_INTERVAL)

  def on_redraw(self, listener):
    self.__redraw_listener = listener

  def start(self):
    self.__event_loop.setName('event_loop')
    self.__event_loop.start()
    self.__event_loop.join()

  def destroy(self):
    """
    Mark the current status as stopped, and wait for the
    event loop to finish
    """
    if self.__status == EventLoopStatus.STOPPED:
      raise RuntimeError('Current context already stopped')

    self.__status = EventLoopStatus.STOPPED
    self.__event_loop.join()


class ViewSize(Enum):
  MATCH_PARENT = 1
  WRAP_CONTENT = 2


class ViewAligmentVertical(Enum):
  TOP = 1
  CENTER = 2
  BOTTOM = 3


class ViewAligmentHorizontal(Enum):
  LEFT = 1
  CENTER = 2
  RIGHT = 3


class ViewMeasurement:
  def __init__(self, position: Tuple[float, float], size: Tuple[float, float], margin: Tuple[float, float, float, float]) -> None:
    """
    *margin* is defined as [top, right, bottom, left]
    """
    self.position = position
    self.margin = margin
    self.size = size

  @staticmethod
  def default():
    return ViewMeasurement((0, 0), ViewSize.WRAP_CONTENT, (0, 0, 0, 0))


class View:
  """
  Something that can be drawn on the screen
  """

  def __init__(self, context: Context, preferred_measure: ViewMeasurement = ViewMeasurement.default()) -> None:
    """
    *context* provides where the view lives in
    *preferred_measure* how the view prefers itself to be drawn, while
    the definitive right is under its parent' control
    """
    self.context = context
    self.preferred_measurement = preferred_measure
    self.actual_measurement = preferred_measure

  def invalidate(self):
    """
    This view is no longer valid and should be redrawn
    """
    self.context.request_redraw()

  def content_size(self) -> Tuple[float, float]:
    """
    Size of its bare content
    """
    return [64, 64]

  def draw(self, canvas: ImageDraw.ImageDraw, scale: float):
    place_holder = resources.get('view-gallery')
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

    canvas.bitmap([(size[0] - place_holder.size[0]) / 2,
                  (size[1] - place_holder.size[1]) / 2], place_holder)
    canvas.rectangle(
        ((0, 0), (size[0], size[1])), fill=None, outline=0, width=6 * scale)


class Group(View):
  def __init__(self, context: Context, preferred_measure: ViewMeasurement = ViewMeasurement.default()) -> None:
    self.__children = []
    super().__init__(context, preferred_measure)

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
      partial = Image.new('L', child.actual_measurement.size, 255)
      partial_canvas = ImageDraw.Draw(partial)
      child.draw(partial_canvas, scale)
      canvas.bitmap(child.actual_measurement.position, partial)

  def content_size(self) -> Tuple[float, float]:
    max = [0, 0]
    for child in self.__children:
      if child.content_size()[0] > max[0]:
        max[0] = child.content_size()[0]
      if child.content_size()[1] > max[1]:
        max[1] = child.content_size()[1]
    return (max[0], max[1])

  def measure(self) -> List[ViewMeasurement]:
    measurements = {}
    for child in self.__children:
      position = child.preferred_measurement.position
      size = child.preferred_measurement.size
      if size == ViewSize.MATCH_PARENT:
        size = self.actual_measurement.size
      elif size == ViewSize.WRAP_CONTENT:
        size = child.content_size()

      remaining_space = util.subtract(
          self.actual_measurement.position,
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

      elif not util.is_inside(remaining_space, child.preferred_measurement.size):
        # the child can not fit the group
        size = remaining_space
      measurements[child] = ViewMeasurement(
          position, size, child.preferred_measurement.margin)

    return measurements


class VGroup(Group):
  def __init__(self, context: Context,
               aligment: ViewAligmentHorizontal = ViewAligmentHorizontal.LEFT,
               preferred_measure: ViewMeasurement = ViewMeasurement.default()) -> None:
    self.aligment = aligment
    return super().__init__(context, preferred_measure)

  def measure(self) -> List[ViewMeasurement]:
    measurements = {}
    measurements_indexed = []

    for index, child in enumerate(super().get_children()):
      position = child.preferred_measurement.position
      size = child.preferred_measurement.size
      margin = child.preferred_measurement.margin
      if size == ViewSize.MATCH_PARENT:
        size = self.actual_measurement.size
      elif size == ViewSize.WRAP_CONTENT:
        size = child.content_size()
      elif type(size) is float:
        # percentage
        size = (self.actual_measurement.size[0]
                * size, child.content_size()[1])

      if index > 0:
        last = measurements_indexed[index - 1]
        last_measure_bottom = last.position[1] + last.size[1] + last.margin[2]
      else:
        last_measure_bottom = 0

      if size[0] + margin[0] + margin[1] > self.actual_measurement.size[0]:
        size = (
            self.actual_measurement.size[0] - margin[0] - margin[1], size[1])

      if self.aligment == ViewAligmentHorizontal.LEFT:
        position = (margin[3], margin[0] + last_measure_bottom)
      elif self.aligment == ViewAligmentHorizontal.RIGHT:
        position = (
            self.actual_measurement.size[0] - size[0], margin[0] + last_measure_bottom)
      elif self.aligment == ViewAligmentHorizontal.CENTER:
        position = (
            (self.actual_measurement.size[0] - size[0]) / 2, margin[0] + last_measure_bottom)

      measurements[child] = ViewMeasurement(position, size, margin)
      measurements_indexed.append(ViewMeasurement(position, size, margin))

    return measurements
