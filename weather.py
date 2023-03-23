from enum import Enum

import resources
from ui import VGroup, Context, ViewMeasurement, ViewAlignmentHorizontal, ImageView, ViewSize, TextView


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
    def __init__(self, day: Day, temperature: float, humidity: float, pressure: float, uv_index: int):
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

    def get_weather(self) -> Weather:
        pass


class TestWeatherProvider(WeatherProvider):
    def __init__(self, weather: Weather):
        location = Location(0, 0, 'Test Land')
        self.__weather = weather
        super().__init__(location, TemperatureUnit.KELVIN)

    def get_weather(self) -> Weather:
        return self.__weather


def get_weather_icon(day: Day):
    if day == Day.CLEAR:
        return resources.get_image('weather-sunny')
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


class WeatherView(VGroup):
    def __init__(self, context: Context, prefer: ViewMeasurement, provider: WeatherProvider):
        super().__init__(context, alignment=ViewAlignmentHorizontal.CENTER, prefer=prefer)
        self.__provider = provider
        self.__icon_view = None
        self.___weather_label_view = None
        self.__additional_label_view = None
        self.refresh()


    def __get_detailed_label(self, weather: Weather):
        return f'{self.__provider.get_location().friendly_name}\n' \
               f'{weather.temperature}°C\n' \
               f'{weather.humidity * 100}% humidity\n' \
               f'{weather.temperature} hPa'

    def refresh(self):
        weather = self.__provider.get_weather()

        if self.__icon_view is None:
            self.__icon_view = ImageView(self.context,
                                         image=get_weather_icon(weather.day),
                                         prefer=ViewMeasurement.default(
                                             width=ViewSize.MATCH_PARENT,
                                             height=64
                                         ))
            self.___weather_label_view = TextView(self.context,
                                                  text=weather.day.name.capitalize(),
                                                  font_size=36,
                                                  prefer=ViewMeasurement.default(width=ViewSize.MATCH_PARENT),
                                                  align_horizontal=ViewAlignmentHorizontal.CENTER)
            self.__additional_label_view = TextView(self.context,
                                                    text=self.__get_detailed_label(weather),
                                                    align_horizontal=ViewAlignmentHorizontal.CENTER,
                                                    line_align=ViewAlignmentHorizontal.CENTER,
                                                    font_size=24,
                                                    prefer=ViewMeasurement.default(width=ViewSize.MATCH_PARENT))
            self.add_views(
                self.__icon_view,
                self.___weather_label_view,
                self.__additional_label_view)
        else:
            self.__icon_view.set_image(get_weather_icon(weather.day))
            self.___weather_label_view.set_text(weather.day.name.capitalize())
            self.__additional_label_view.set_text(self.__get_detailed_label(weather))

    def set_provider(self, provider: WeatherProvider):
        if self.__provider != provider:
            self.__provider = provider
            self.invalidate()
