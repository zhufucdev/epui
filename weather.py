import datetime
import json

import requests

import resources
from ui import VGroup, Context, ViewMeasurement, ViewAlignmentHorizontal, ImageView, ViewSize, TextView, HGroup, \
    Surface, ViewAlignmentVertical
from charts import TrendChartsView, ChartsLineType

from enum import Enum
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
    HAZY = 9
    FOGGY = 10
    DUSTY = 11
    SANDY = 12
    WINDY = 13
    UNKNOWN = 14


class TemperatureUnit(Enum):
    CELSIUS = 0
    FAHRENHEIT = 1
    KELVIN = 2


class WeatherEffectiveness(Enum):
    CURRENT = 0
    HOURLY = 1
    DAILY = 2


class Weather:
    def __init__(self,
                 time: pytime.struct_time = pytime.localtime(),
                 effect: WeatherEffectiveness = WeatherEffectiveness.CURRENT,
                 day: Day = Day.CLEAR,
                 temperature: float = 22,
                 humidity: float = 0.2,
                 pressure: float = 10,
                 uv_index: int = 5):
        """
        All these default parameters are for testing purpose, and
        should be set by the weather provider.
        :param day: the sky-con
        :param effect: role this weather data's playing
        :param temperature: value of temperature, unit dependent on the provider
        :param humidity: range from 0-1 in percentage
        :param pressure: air pressure in hPa
        :param uv_index: range from 0-10, aka ultraviolet index
        """
        self.time = time
        self.effect = effect
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


class CachedWeatherProvider(WeatherProvider):
    def __init__(self, location: Location, temperature_unit: TemperatureUnit, cache_invalidate_interval: float = 3600):
        super().__init__(location, temperature_unit)
        self.cache_invalidation = cache_invalidate_interval
        self.__update_time = None
        self.__cache = None

    def invalidate(self) -> List[Weather]:
        pass

    def get_weather(self):
        if self.__update_time is not None \
                and pytime.time() - self.__update_time < self.cache_invalidation:
            return self.__cache
        self.__update_time = pytime.time()
        new_data = self.invalidate()
        self.__cache = new_data
        return new_data


class TestWeatherProvider(WeatherProvider):
    def __init__(self, weather: Weather):
        self.__weather = weather
        location = Location(0, 0, 'Test Land')
        super().__init__(location, TemperatureUnit.CELSIUS)

    def get_weather(self) -> List[Weather]:
        return [self.__weather]


class CaiYunWeatherProvider(CachedWeatherProvider):
    def __init__(self, location: Location, api_key: str, cache_invalidate_interval: float = 3600):
        super().__init__(location, TemperatureUnit.CELSIUS, cache_invalidate_interval)
        self.api_key = api_key

    def __get_api_url(self):
        return f'https://api.caiyunapp.com/v2.6/{self.api_key}/' \
               f'{self.get_location().longitude},{self.get_location().latitude}'

    @staticmethod
    def __caiyun_get_day(raw: str) -> Day:
        """
        See https://docs.caiyunapp.com/docs/tables/skycon/ for full list
        :param raw: caiyun's response
        :return: my interface
        """
        raw = raw.lower()
        if 'clear' in raw:
            return Day.CLEAR
        elif 'cloudy' in raw:
            return Day.CLOUDY
        elif 'haze' in raw:
            return Day.HAZY
        elif raw == 'light_rain':
            return Day.LIGHTLY_RAINY
        elif raw == 'moderate_rain':
            return Day.RAINY
        elif raw == 'heavy_rain' or raw == 'storm_rain':
            return Day.HEAVILY_RAINY
        elif raw == 'fog':
            return Day.FOGGY
        elif raw == 'light_snow':
            return Day.LIGHTLY_SNOWY
        elif raw == 'moderate_snow':
            return Day.SNOWY
        elif raw == 'heavy_snow' or raw == 'storm_snow':
            return Day.HEAVILY_SNOWY
        elif raw == 'dust':
            return Day.DUSTY
        elif raw == 'sand':
            return Day.SANDY
        elif raw == 'wind':
            return Day.WINDY
        else:
            return Day.UNKNOWN

    def invalidate(self) -> List[Weather]:
        response = requests.get(self.__get_api_url() + '/weather?dailysteps=3&hourlysteps=24&minutely=false')
        if not response.ok:
            raise IOError('Realtime API not responding')

        api_callback = json.loads(response.text)
        result_realtime = api_callback['result']['realtime']
        result_hourly = api_callback['result']['hourly']
        result_daily = api_callback['result']['daily']
        current_weather = Weather(
            time=pytime.localtime(),
            effect=WeatherEffectiveness.CURRENT,
            temperature=result_realtime['temperature'],
            day=self.__caiyun_get_day(result_realtime['skycon']),
            humidity=result_realtime['humidity'],
            pressure=result_realtime['pressure'] / 100,
            uv_index=int(result_realtime['life_index']['ultraviolet']['index'])
        )
        hourly_weather = []
        daily_weather = []

        def parse(target_set: List[Weather], source: Dict, effect: WeatherEffectiveness):
            def pick(unit: Dict):
                if 'value' in unit:
                    return unit['value']
                elif 'avg' in unit:
                    return unit['avg']
                else:
                    raise ValueError(unit)

            for i in range(len(source['precipitation'])):
                precipitation = source['precipitation'][i]
                if 'datetime' in precipitation:
                    time = datetime.datetime.fromisoformat(precipitation['datetime']).timetuple()
                elif 'date' in precipitation:
                    time = datetime.datetime.fromisoformat(precipitation['date']).timetuple()
                else:
                    raise ValueError(precipitation)

                temperature = pick(source['temperature'][i])
                humidity = pick(source['humidity'][i])
                sky_con = pick(source['skycon'][i])
                pressure = pick(source['pressure'][i])
                target_set.append(
                    Weather(
                        time, effect, self.__caiyun_get_day(sky_con),
                        temperature, humidity, pressure, -1
                    )
                )

        parse(hourly_weather, result_hourly, WeatherEffectiveness.HOURLY)
        parse(daily_weather, result_daily, WeatherEffectiveness.DAILY)

        return [current_weather] + hourly_weather + daily_weather


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
    elif day == Day.WINDY:
        return resources.get_image('weather-windy')
    elif day == Day.HAZY:
        return resources.get_image('weather-hazy')
    elif day == Day.FOGGY:
        return resources.get_image('weather-fog')
    elif day == Day.DUSTY:
        return resources.get_image('weather-dust')
    else:
        return resources.get_image('weather-alert')


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
               f'{int(weather.pressure)} hPa\n' \
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
        weather = next(weather for weather in self.__provider.get_weather()
                       if weather.effect == WeatherEffectiveness.CURRENT)

        if self.__icon_view is None:
            self.__add_views(weather)
        else:
            self.__icon_view.set_image(get_weather_icon(weather.day))
            self.__day_label_view.set_text(self.__get_detailed_label(weather))

    def set_provider(self, provider: WeatherProvider):
        if self.__provider != provider:
            self.__provider = provider
            self.invalidate()


class WeatherTrendView(TrendChartsView):
    def __init__(self, context: Context,
                 title: str, provider: WeatherProvider,
                 effect: WeatherEffectiveness,
                 value: Callable[[Weather], float],
                 prefer: ViewMeasurement = ViewMeasurement.default()):
        super().__init__(context, title, [], line_type=ChartsLineType.BEZIER_CURVE, prefer=prefer)
        self.__provider = provider
        self.__effect = effect
        self.__value = value
        self.refresh()

    @staticmethod
    def label(w: Weather) -> int:
        current_time = pytime.localtime()
        return w.time.tm_hour - current_time.tm_hour + 24 * (w.time.tm_yday - current_time.tm_yday) + \
            365 * (w.time.tm_year - current_time.tm_year)

    def refresh(self):
        data = [(self.label(w), self.__value(w)) for w in self.__provider.get_weather()
                if w.effect == self.__effect]
        self.set_data(data)
