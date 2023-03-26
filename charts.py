import numbers
from enum import Enum
from typing import *
from PIL import ImageDraw, ImageFont, Image

import ui
import util
from ui import Context, View, ViewMeasurement, COLOR_TRANSPARENT, overlay


class AxisPosition(Enum):
    LEFT = 0
    RIGHT = 1
    TOP = 2
    BOTTOM = 3


class Axis:
    def __init__(self, position: AxisPosition | None, label: str, enabled: bool = True):
        self.enabled = enabled
        self.position = position
        self.label = label
        self.min = 0
        self.max = 0

    def __eq__(self, other):
        if type(other) is not type(self):
            return False
        return self.enabled == other.enabled and \
            self.position == other.position

    @staticmethod
    def disabled() -> 'Axis':
        return Axis(None, '', False)


class ChartsConfiguration:
    def __init__(self, title: str, x_axis: Axis, y_axis: Axis, axis_label_font_size: int = 20):
        self.title = title
        self.x_axis = x_axis
        self.y_axis = y_axis
        self.axis_label_font_size = axis_label_font_size

    def __eq__(self, other):
        if type(other) is not type(self):
            return False
        return self.title == other.title and \
            self.x_axis == other.x_axis and \
            self.y_axis == other.y_axis


class ChartsView(View):
    """
    The base class for all charts view
    """

    def __init__(self, context: Context,
                 configuration: ChartsConfiguration,
                 prefer: ViewMeasurement = ViewMeasurement.default()):
        super().__init__(context, prefer)
        self.__configuration = configuration

    def get_configuration(self) -> ChartsConfiguration:
        return self.__configuration

    def set_configuration(self, configuration: ChartsConfiguration):
        if self.__configuration != configuration:
            self.__configuration = configuration
            self.invalidate()

    def x_axis_size(self) -> int:
        return 64

    def y_axis_size(self) -> int:
        return 64

    def draw_x_axis(self, canvas: ImageDraw.ImageDraw, bounds: Tuple[int, int], scale: float):
        pass

    def draw_y_axis(self, canvas: ImageDraw.ImageDraw, bounds: Tuple[int, int], scale: float):
        pass

    def draw_body(self, canvas: ImageDraw.ImageDraw, bounds: Tuple[int, int], scale: float):
        pass

    def draw(self, canvas: ImageDraw.ImageDraw, scale: float):
        body_bounds = self.__draw_axis(canvas, scale)
        body_canvas = Image.new('L', (body_bounds[2], body_bounds[3]), COLOR_TRANSPARENT)
        self.draw_body(ImageDraw.Draw(body_canvas), (body_bounds[2], body_bounds[3]), scale)
        overlay(canvas._image, body_canvas, (body_bounds[0], body_bounds[1]))

    def __draw_axis(self, canvas: ImageDraw.ImageDraw, scale: float) -> Tuple[int, int, int, int]:
        x_axis = [0] * 4
        y_axis = [0] * 4
        body_bounds = [0] * 4
        bounds = self.actual_measurement.size
        if self.__configuration.x_axis.enabled and self.__configuration.y_axis.enabled:
            x_axis[2] = bounds[0] - self.y_axis_size()
            x_axis[3] = self.x_axis_size()
            y_axis[2] = self.y_axis_size()
            y_axis[3] = bounds[1] - self.x_axis_size()

            if self.__configuration.x_axis.position == AxisPosition.BOTTOM:
                x_axis[1] = bounds[1] - self.x_axis_size()
                y_axis[1] = bounds[1] - self.y_axis_size()
            else:
                x_axis[1] = 0
                y_axis[1] = self.x_axis_size()
            if self.__configuration.y_axis.position == AxisPosition.LEFT:
                x_axis[0] = self.y_axis_size()
                y_axis[0] = 0
            else:
                x_axis[0] = 0
                y_axis[0] = bounds[0] - self.y_axis_size()

        elif self.__configuration.x_axis.enabled and not self.__configuration.y_axis.enabled:
            if self.__configuration.x_axis.position == AxisPosition.BOTTOM:
                x_axis[0] = 0
                x_axis[1] = bounds[1] - self.x_axis_size()
                x_axis[2] = bounds[0]
                x_axis[3] = self.x_axis_size()
            else:
                x_axis[0] = 0
                x_axis[1] = 0
                x_axis[2] = bounds[0]
                x_axis[3] = self.x_axis_size()
        elif not self.__configuration.x_axis.enabled and self.__configuration.y_axis.enabled:
            if self.__configuration.y_axis.position == AxisPosition.LEFT:
                y_axis[0] = 0
                y_axis[1] = 0
                y_axis[2] = self.y_axis_size()
                y_axis[3] = bounds[1]
            else:
                y_axis[0] = bounds[0] - self.y_axis_size()
                y_axis[1] = 0
                y_axis[2] = self.y_axis_size()
                y_axis[3] = bounds[1]
        else:
            return 0, 0, int(bounds[0]), int(bounds[1])

        if util.is_positive((x_axis[2], x_axis[3])):
            x_canvas = Image.new('L', (x_axis[2], x_axis[3]), COLOR_TRANSPARENT)
            self.draw_x_axis(ImageDraw.Draw(x_canvas), (x_axis[2], x_axis[3]), scale)
            overlay(canvas._image, x_canvas, (x_axis[0], x_axis[1]))
        if util.is_positive((y_axis[2], y_axis[3])):
            y_canvas = Image.new('L', (y_axis[2], y_axis[3]), COLOR_TRANSPARENT)
            self.draw_y_axis(ImageDraw.Draw(y_canvas), (y_axis[2], y_axis[3]), scale)
            overlay(canvas._image, y_canvas, (y_axis[0], y_axis[1]))
        return body_bounds[0], body_bounds[1], body_bounds[2], body_bounds[3]


IndependentVar = int | float | str
DependentVar = int | float
ChartData = List[Tuple[IndependentVar, DependentVar]]


def update_axis_bounds(data: ChartData, y_axis: Axis, x_axis: Axis):
    y_axis.min = data[0][1]
    y_axis.max = x_axis.min
    for i in range(1, len(data)):
        y_axis.min = min(y_axis.min, data[i][1])
        y_axis.max = max(y_axis.max, data[i][1])
    if y_axis.min == y_axis.max:
        return

    if isinstance(data[0][0], numbers.Number):
        x_axis.min = data[0][0]
        x_axis.max = x_axis.min
        for i in range(1, len(data)):
            x_axis.min = min(x_axis.min, data[i][0])
            x_axis.max = max(x_axis.max, data[i][0])


def draw_straight_line(
        canvas: ImageDraw.ImageDraw,
        bounds: Tuple[int, int],
        config: ChartsConfiguration,
        data: ChartData,
        fill: int, width: int, ):
    x_axis, y_axis = config.x_axis, config.y_axis
    y_len = y_axis.max - y_axis.min
    if y_len == 0:
        canvas.line(
            xy=[(0, int(bounds[1] / 2)), (bounds[0], int(bounds[1] / 2))],
            fill=fill,
            width=width
        )
        return

    if isinstance(data[0][0], numbers.Number):
        x_len = x_axis.max - x_axis.min
        canvas.line(
            xy=[(int((data[0] - x_axis.min) / x_len * bounds[0]), int(bounds[1] * (y_axis.max - data[1]) / y_len))
                for data in data],
            fill=fill,
            width=width
        )
    else:
        x_segment = bounds[0] / (len(data) - 1)
        canvas.line(
            xy=[(int(i * x_segment), int(bounds[1] * (y_axis.max - data[i][1]) / y_len))
                for i in range(0, len(data))],
            fill=fill,
            width=width
        )


def draw_bezier_curve(
        canvas: ImageDraw.ImageDraw,
        bounds: Tuple[int, int],
        config: ChartsConfiguration,
        data: ChartData,
        fill: int, width: int):
    x, y = config.x_axis, config.y_axis
    if y.max == y.min:
        draw_straight_line(canvas, bounds, config, data, fill, width)

    def manipulate(t: float, p0: Tuple[float, float], p1: Tuple[float, float], pos: str = 'm') -> Tuple[int, int]:
        u = 1 - t
        if pos == 's':
            pc1 = (p0[0], p0[1] * 0.8 + p1[1] * 0.2)
            pc2 = (p0[0] * 0.2 + p1[0] * 0.8, p1[1])
        elif pos == 'e':
            pc1 = (p0[0] * 0.8 + p1[0] * 0.2, p0[1])
            pc2 = (p1[0], p0[1] * 0.2 + p1[1] * 0.8)
        else:
            pc1 = (p0[0] * 0.8 + p1[0] * 0.2, p0[1])
            pc2 = (p0[0] * 0.2 + p1[0] * 0.8, p1[1])

        result = util.multiply(p0, u * u * u)
        result = util.plus(result, util.multiply(pc1, 3 * u * u * t))
        result = util.plus(result, util.multiply(pc2, 3 * u * t * t))
        result = util.plus(result, util.multiply(p1, t * t * t))
        return util.int_vector(result)

    cache = {
        'last_index': 0
    }
    if isinstance(data[0][0], numbers.Number):
        x_len = config.x_axis.max - config.x_axis.min
        y_len = config.y_axis.max - config.y_axis.min

        def map_to_canvas(point: Tuple[float, float]) -> Tuple[float, float]:
            return (point[0] - config.x_axis.min) / x_len * bounds[0], \
                   (config.y_axis.max - point[1]) / y_len * bounds[1]

        def iterate(t: float) -> Tuple[int, int]:
            _x = x_len * t + config.x_axis.min
            for i in range(cache['last_index'], len(data) - 1):
                if data[i][0] <= _x < data[i + 1][0]:
                    cache['last_index'] = i
                    if i == 0:
                        pos = 's'
                    elif i == len(data) - 2:
                        pos = 'e'
                    else:
                        pos = 'm'
                    return manipulate((_x - data[i][0]) / (data[i + 1][0] - data[i][0]),
                                      map_to_canvas(data[i]), map_to_canvas(data[i + 1]), pos)
    else:
        segment = 1 / (len(data) - 1)
        y_len = config.y_axis.max - config.y_axis.min

        def map_to_canvas(point: Tuple[int, float]) -> Tuple[float, float]:
            return point[0] / (len(data) - 1) * bounds[0], (config.y_axis.max - point[1]) / y_len * bounds[1]

        def iterate(t: float) -> Tuple[int, int]:
            u = t % segment / segment
            _x = int(t * (len(data) - 1))
            if _x == 0:
                pos = 's'
            elif _x >= len(data) - 2:
                pos = 'e'
                if _x >= len(data) - 1:
                    _x = len(data) - 2
            else:
                pos = 'm'
            return manipulate(u, map_to_canvas((_x, data[_x][1])), map_to_canvas((_x + 1, data[_x + 1][1])), pos)

    canvas.line(
        xy=[iterate(i / bounds[0]) for i in range(0, bounds[0])],
        width=width,
        fill=fill
    )


class ChartsLineType(Enum):
    STRAIGHT = 0
    BEZIER_CURVE = 1


class TrendChartsView(ChartsView):
    """
    A ChartsView that only shows a trendy line
    """

    def __init__(self, context: Context,
                 title: str,
                 data: ChartData,
                 line_width: float = 2,
                 line_fill: int = 0,
                 line_type: ChartsLineType = ChartsLineType.STRAIGHT,
                 prefer: ViewMeasurement = ViewMeasurement.default()):
        super().__init__(
            context,
            configuration=ChartsConfiguration(
                title=title,
                x_axis=Axis.disabled(),
                y_axis=Axis.disabled()
            ),
            prefer=prefer
        )
        self.__line_type = line_type
        self.__data = data
        self.__line_width = line_width
        self.__line_fill = line_fill

    def get_line_width(self):
        return self.__line_width

    def set_line_width(self, line_width: float):
        if self.__line_width != line_width:
            self.__line_width = line_width
            self.invalidate()

    def get_line_fill(self):
        return self.__line_fill

    def set_line_fill(self, line_fill: int):
        if self.__line_fill != line_fill:
            self.__line_fill = line_fill
            self.invalidate()

    def get_data(self):
        return self.__data

    def set_data(self, data: List[Tuple[IndependentVar, DependentVar]]):
        self.__data = data
        self.invalidate()

    def draw_body(self, canvas: ImageDraw.ImageDraw, bounds: Tuple[int, int], scale: float):
        font = ImageFont.truetype(ui.TextView.default_font, size=24 * scale)
        title_bounds = canvas.textbbox((0, 0), self.get_configuration().title, font=font)
        canvas.text(
            xy=(int((bounds[0] - title_bounds[2]) / 2), bounds[1] - title_bounds[3] - int(3 * scale)),
            font=font,
            text=self.get_configuration().title,
        )
        if View.draw_bounds_box:
            canvas.rectangle((0, 0, bounds[0], bounds[1]), outline=0, width=3 * scale)
        if len(self.__data) <= 0:
            return
        x_axis, y_axis = self.get_configuration().x_axis, self.get_configuration().y_axis

        update_axis_bounds(self.__data, y_axis, x_axis)
        if self.__line_type == ChartsLineType.STRAIGHT:
            draw_straight_line(canvas, bounds, self.get_configuration(), self.__data,
                               self.__line_fill, int(self.__line_width * scale))
        else:
            draw_bezier_curve(canvas, bounds, self.get_configuration(), self.__data,
                              self.__line_fill, int(self.__line_width * scale))