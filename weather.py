from enum import Enum

import resources
from ui import VGroup, Context, ViewMeasurement, ViewAlignmentHorizontal, ImageView, ViewSize, TextView, HGroup, \
    Surface, ViewAlignmentVertical
import time as pytime
from typing import *


class Location:
    def __init__(self, latitude: float, longitude: float, friendly_name: str = None):
        self.latitude = latitude
        self.longitude = longitude
        self.friendly_name = friendly_name


class Day(Enum):
    CLEAR = 0
    CLOUDY = 1
    LIGHTLY_RAINY = 2
    RAINY = 3
    HEAVILY_RAINY = 4
    SNOWY_RAINY = 5
    LIGHTLY_SNOWY = 6
    SNOWY = 7
    HEAVILY_SNOWY = 8


class TemperatureUnit(Enum):
    CELSIUS = 0
    FAHRENHEIT = 1
    KELVIN = 2


class Weather:
    def __init__(self,
                 time: Tuple = pytime.localtime(),
                 day: Day = Day.CLEAR,
                 temperature: float = 22,
                 humidity: float = 0.2,
                 pressure: float = 10,
                 uv_index: int = 5):
        """
        All these default parameters are for testing purpose, and
        should be set by the weather provider.
        """
        self.time = time
        self.day = day
        self.temperature = temperature
        self.humidity = humidity
        self.pressure = pressure
        self.uv_index = uv_index


class WeatherProvider:
    def __init__(self, location: Location, temperature_unit: TemperatureUnit):
        self.__location = location
        self.__temperature_unit = temperature_unit

    def get_location(self):
        return self.__location

    def get_temperature_unit(self):
        return self.__temperature_unit

    def get_weather(self) -> List[Weather]:
        """
        Refresh the weather query
        :return: list of weather infos, sorted from the most recent to the farthest future,
         length of the which is undefined
        """
        pass


class TestWeatherProvider(WeatherProvider):
    def __init__(self, weather: Weather):
        location = Location(0, 0, 'Test Land')
        self.__weather = weather
        super().__init__(location, TemperatureUnit.CELSIUS)

    def get_weather(self) -> List[Weather]:
        return [self.__weather]


def get_weather_icon(day: Day):
    if day == Day.CLEAR:
        return resources.get_image_tint('weather-sunny', 100)
    elif day == Day.CLOUDY:
        return resources.get_image('weather-cloudy')
    elif day == Day.RAINY or day == Day.LIGHTLY_RAINY:
        return resources.get_image('weather-rainy')
    elif day == Day.HEAVILY_RAINY:
        return resources.get_image('weather-pouring')
    elif day == Day.SNOWY or day == Day.LIGHTLY_SNOWY:
        return resources.get_image('weather-snowy')
    elif day == Day.HEAVILY_SNOWY:
        return resources.get_image('weather-snowy-heavy')
    elif day == Day.SNOWY_RAINY:
        return resources.get_image('weather-snowy-rainy')


class LargeWeatherView(HGroup):
    def __init__(self, context: Context, provider: WeatherProvider,
                 prefer: ViewMeasurement = ViewMeasurement.default()):
        super().__init__(context, alignment=ViewAlignmentVertical.CENTER, prefer=prefer)
        self.__provider = provider
        self.__icon_view = None
        self.__day_label_view = None
        self.__subtitle_label_view = None
        self.refresh()

    def __get_detailed_label(self, weather: Weather):
        temp_unit = self.__provider.get_temperature_unit()
        if temp_unit == TemperatureUnit.CELSIUS:
            unit_str = '°C'
        elif temp_unit == TemperatureUnit.FAHRENHEIT:
            unit_str = '°F'
        else:
            unit_str = 'K'

        return f'{weather.temperature} {unit_str}\n' \
               f'{int(weather.humidity * 100)} %\n' \
               f'{weather.pressure} hPa\n' \
               f'{weather.uv_index} UV'

    def __add_views(self, weather: Weather):
        title_group = VGroup(self.context, alignment=ViewAlignmentHorizontal.RIGHT)
        self.__icon_view = ImageView(self.context,
                                     image=get_weather_icon(weather.day),
                                     prefer=ViewMeasurement.default(
                                         width=100,
                                         height=100
                                     ))
        self.__day_label_view = TextView(self.context,
                                         text=weather.day.name.capitalize(),
                                         font=TextView.default_font_bold,
                                         font_size=36)
        self.__subtitle_label_view = TextView(self.context,
                                              text=self.__get_detailed_label(weather),
                                              font_size=20,
                                              line_align=ViewAlignmentHorizontal.RIGHT)
        self.add_views(
            self.__icon_view,
            Surface(self.context,
                    prefer=ViewMeasurement.default(
                        width=3,
                        height=ViewSize.MATCH_PARENT,
                        margin_right=4,
                        margin_left=4,
                    ),
                    fill=0),
            title_group
        )
        title_group.add_views(
            self.__day_label_view,
            self.__subtitle_label_view
        )

    def refresh(self):
        weather = self.__provider.get_weather()[0]

        if self.__icon_view is None:
            self.__add_views(weather)
        else:
            self.__icon_view.set_image(get_weather_icon(weather.day))
            self.__day_label_view.set_text(self.__get_detailed_label(weather))

    def set_provider(self, provider: WeatherProvider):
        if self.__provider != provider:
            self.__provider = provider
            self.invalidate()
