import datetime
import logging
import time as pytime
from enum import Enum
from typing import *

import google.auth.exceptions
import googleapiclient.discovery as gcp
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

import cache
from ui import Context, Group, ViewMeasurement, TextView, Surface, \
    ViewSize, VGroup, ViewAlignmentHorizontal, ViewAlignmentVertical, ImageFont


class EventTimeSpan:
    def __init__(self, is_full_day: bool):
        self.__is_full_day = is_full_day

    def is_full_day(self) -> bool:
        return self.__is_full_day


class FullDayTimeSpan(EventTimeSpan):
    def __init__(self, date: pytime.struct_time, span: int):
        self.__date = date
        self.__span = span
        super().__init__(True)

    def __contains__(self, item: pytime.struct_time):
        return 0 <= pytime.mktime(item) - pytime.mktime(self.__date) <= datetime.timedelta(days=self.__span).seconds

    def get_span(self) -> int:
        return self.__span

    def start_date(self):
        return self.__date

    def __eq__(self, other):
        return type(other) == FullDayTimeSpan and other.get_span() == self.__span \
            and other.start_date() == self.__date


class TwoStepTimeSpan(EventTimeSpan):
    def __init__(self, start: pytime.struct_time, end: pytime.struct_time):
        self.__start = start
        self.__end = end
        super().__init__(False)

    def __contains__(self, item: pytime.struct_time):
        t_start = pytime.mktime(self.__start)
        t_end = pytime.mktime(self.__end)
        return 0 <= pytime.mktime(item) - t_start < t_end - t_start

    def start_time(self):
        return self.__start

    def end_time(self):
        return self.__end

    def __eq__(self, other):
        return type(other) == TwoStepTimeSpan and other.start_time() == self.__start \
            and other.end_time() == self.__end


class EventType(Enum):
    PERSONAL = 0
    HOLIDAY = 1


class Event:
    def __init__(self, name: str, location: str | None, time: EventTimeSpan):
        self.__name = name
        self.__location = location
        self.__time = time

    def get_name(self):
        return self.__name

    def get_location(self):
        return self.__location

    def get_time(self):
        return self.__time

    def __eq__(self, other):
        return type(other) == Event and other.get_name() == self.__name \
            and other.get_time() == self.__time \
            and other.get_location() == self.__location


class CalendarProvider:
    """
    A CalendarProvider supplies `Event` for a `CalendarView`
    """

    def __init__(self, name: str, max_results: int):
        """
        Create a calendar provider
        :param name: what to call it
        :param max_results: max count of items the func:`get_events` returns
        """
        self.__name = name
        self.__max_results = max_results

    def get_name(self):
        return self.__name

    def get_max_results(self):
        """
        the func:`get_events` should return no more than this number of events
        :return: the max count of results
        """
        return self.__max_results

    def get_events(self) -> List[Event]:
        """
        A list of events this provider supplies
        :return: the events, counting no more than `max_results`
        """
        pass


class FilterProvider(CalendarProvider):
    def __init__(self, name: str, parent: CalendarProvider, filter: Callable[[Event], bool]):
        super().__init__(name, parent.get_max_results())
        self.__parent = parent
        self.__filter = filter

    def get_events(self) -> List[Event]:
        return list(filter(self.__filter, self.__parent.get_events()))


class GoogleCalendarProvider(CalendarProvider):
    """
    A working implementation of CalendarProvider than involves Google Workspace
    """

    def __init__(self, name: str = None,
                 credentials_file: str = None, calendar_id: str = 'primary',
                 max_results: int = 10,
                 callback_addr: str = 'localhost', callback_port: int = 3891, api_key: str = None):
        """
        Creates a GoogleCalendarProvider
        :param name: what to call it
        :param credentials_file: path to the credentials file. To get one, see
        https://developers.google.com/calendar/api/quickstart/python#set_up_your_environment

        :param calendar_id: the calendar id which the owner of the credentials ever created
        :param max_results: how many results at most should the `get_events` function return
        :param callback_addr: where to run a http server for callback, typically accessed
        by the validating browser
        :param callback_port: on which port to run the http server for callback
        :param api_key: the api key to use. If set, will ignore all OAuth2 stuff and use the api key instead.
        Note that this method can only access non-private calendars, so make sure the calendar is public
        """
        self.__calendar_id = calendar_id
        self.__credentials_file = credentials_file
        self.__callback_addr = callback_addr
        self.__callback_port = callback_port
        self.__api_key = api_key

        self.__creds = None
        self.__service = None
        super().__init__(name, max_results)

    def __login(self):
        if self.__api_key is None:
            if cache.exits('gcp_token.json'):
                self.__creds = Credentials.from_authorized_user_file(cache.get_file('gcp_token.json'))

            updated = False
            if not self.__creds or not self.__creds.valid:
                updated = True
                if self.__creds and self.__creds.expired and self.__creds.refresh_token:
                    self.__creds.refresh(Request())
                else:
                    scope = ['https://www.googleapis.com/auth/calendar.readonly']
                    flow = InstalledAppFlow.from_client_secrets_file(self.__credentials_file, scope)
                    self.__creds = flow.run_local_server(bind_addr=self.__callback_addr, port=self.__callback_port)
                    with cache.open_cache('gcp_token.json', 'w') as token:
                        token.write(self.__creds.to_json())

            if not self.__service or updated:
                self.__service = gcp.build('calendar', 'v3', credentials=self.__creds)
        else:
            self.__service = gcp.build('calendar', 'v3', developerKey=self.__api_key)

    @staticmethod
    def __parse_event(data: Dict[str, Any]) -> Event:
        if 'dateTime' in data['start'] and 'T' in data['start']['dateTime']:
            full_format = '%Y-%m-%dT%H:%M:%S%z'
            start, end = pytime.strptime(data['start']['dateTime'], full_format), \
                pytime.strptime(data['end']['dateTime'], full_format)
            span = TwoStepTimeSpan(start, end)
        else:
            daily_format = '%Y-%m-%d'
            start, end = pytime.strptime(data['start']['date'], daily_format), \
                pytime.strptime(data['end']['date'], daily_format)
            span = FullDayTimeSpan(date=start, span=(pytime.mktime(end) - pytime.mktime(start)) // 86400)

        if 'location' in data:
            location = data['location']
        else:
            location = ''

        return Event(data['summary'], location, span)

    def get_events(self) -> List[Event]:
        try:
            self.__login()
        except google.auth.exceptions.TransportError as e:
            logging.warning(f'Google calendar failed due to network error: {e}')
            return []
        except google.auth.exceptions.RefreshError as e:
            logging.warning(f'Failed to refresh Google calendar: {e}')
            return []
        except google.auth.exceptions.GoogleAuthError as e:
            logging.warning(f'Failed to authorized Google calendar: {e}')
            return []

        try:
            raw = self.__service.events().list(
                calendarId=self.__calendar_id,
                timeMin=datetime.datetime.utcnow().isoformat() + "Z",
                maxResults=self.get_max_results(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = raw.get('items', [])

            return [self.__parse_event(e) for e in events]
        except HttpError as e:
            logging.warning(f'Unable to fetch calendar events: {e}')
            return []


class CalenderStripeView(Group):
    """
    A view that displays a single event in high contrast
    """

    def __init__(self, context: Context, event: Event,
                 font_size: int = 16, font=TextView.default_font,
                 prefer: ViewMeasurement = ViewMeasurement.default(),
                 is_split: bool = False, is_square: bool = False):
        """
        Create a CalendarStripeView
        :param context: where the view lives
        :param event: the event to display
        :param font_size: font size of the summary and time
        :param font: file to the desired font family
        :param prefer: preferred layout method
        :param is_split: whether to split the view into two parts
        :param is_square: whether to make the view square
        """
        super().__init__(context, prefer)
        self.__event = event
        radius = 10
        if is_square:
            radius = 0

        if is_split:
            self.__name_text_view = TextView(context,
                                             text=self.__get_event_name(),
                                             font_size=font_size,
                                             font=font,
                                             fill=self.context.bg_color,
                                             prefer=ViewMeasurement.default(
                                                 margin_top=5,
                                                 margin_bottom=2,  # idk why, but it just aligned
                                                 margin_left=10,
                                                 margin_right=5
                                             ))
            self.__span_text_view = TextView(context,
                                             text=self.__get_event_time(),
                                             font_size=font_size,
                                             font=font,
                                             fill=self.context.bg_color,
                                             align_horizontal=ViewAlignmentHorizontal.RIGHT,
                                             prefer=ViewMeasurement.default(
                                                 margin_top=2,
                                                 margin_bottom=5,
                                                 margin_right=10,
                                                 width=ViewSize.MATCH_PARENT,
                                                 height=ViewSize.MATCH_PARENT
                                             ))
            self.add_views(
                Surface(context,
                        radius=radius,
                        fill=self.context.fg_color,
                        prefer=ViewMeasurement.default(size=ViewSize.MATCH_PARENT)),
                self.__name_text_view,
                self.__span_text_view)
        else:
            self.__text_view = TextView(context,
                                        text=self.__get_text(),
                                        font_size=font_size,
                                        font=font,
                                        fill=self.context.bg_color,
                                        prefer=ViewMeasurement.default(
                                            margin_top=5,
                                            margin_bottom=2,  # idk why, but it just aligned
                                            margin_left=10,
                                            margin_right=5
                                        ))
            self.add_views(
                Surface(context,
                        radius=radius,
                        fill=self.context.fg_color,
                        prefer=ViewMeasurement.default(size=ViewSize.MATCH_PARENT)),
                self.__text_view
            )

    def get_font(self):
        """
        Font family of the summary and time
        :return: the path to the font file
        """
        return self.__text_view.get_font()

    def set_font(self, font: str):
        """
        Font family of the summary and time. This may cause a full redraw
        :param font: desired font file
        """
        return self.__text_view.set_font(font)

    def __get_event_name(self) -> str:
        return f'{self.__event.get_name()}'

    def __get_event_time(self) -> str:
        span = self.__event.get_time()
        if type(span) is FullDayTimeSpan:
            days = span.get_span()
            if days > 1:
                return f'{days} days'
            else:
                return f'today'
        else:
            t_format = '%H:%M'
            return f'{pytime.strftime(t_format, span.start_time())} - ' \
                   f'{pytime.strftime(t_format, span.end_time())}'

    def __get_text(self) -> str:
        span = self.__event.get_time()
        if type(span) is FullDayTimeSpan:
            days = span.get_span()
            if days > 1:
                return f'{self.__event.get_name()} - {days} days'
            else:
                return f'{self.__event.get_name()} - today'
        else:
            t_format = '%H:%M'
            return f'{self.__event.get_name()} ' \
                   f'{pytime.strftime(t_format, span.start_time())} - ' \
                   f'{pytime.strftime(t_format, span.end_time())}'

    def get_event(self):
        """
        The event to display
        :return: the current event
        """
        return self.__event

    def set_event(self, event: Event):
        """
        The event to display. This may cause a full redraw
        :param event: the desired event
        """
        if self.__event != event:
            self.__event = event
            self.invalidate()


class CalendarView(VGroup):
    """
    A CalendarView is a vertical list of `CalendarStripeView` to display a series of events
    """

    def __init__(self, context: Context, provider: CalendarProvider,
                 font_size: int = 16, font: str = TextView.default_font,
                 prefer: ViewMeasurement = ViewMeasurement.default(),
                 is_split: bool = False, is_square: bool = False):
        """
        Creates a CalendarView
        :param context: where the view lives in
        :param provider: the event provider
        :param font_size: font size of the summary and time
        :param font: file path to the desired font family. Only be a TrueTypeFont is acceptable
        :param prefer: preferred layout
        :param is_split: if the view should be split
        """
        self.__provider = provider
        self.__font = font
        self.__font_size = font_size
        self.__is_split = is_split
        self.__is_square = is_square
        super().__init__(context, prefer=prefer)
        self.refresh()

    def get_provider(self):
        """
        The event provider
        :return: current provider
        """
        return self.__provider

    def set_provider(self, provider: CalendarProvider):
        """
        The event provider. May lead to a full redraw
        :param provider: desired provider
        """
        if provider != self.__provider:
            self.__provider = provider
            self.refresh()

    def __get_view(self, ev: Event):
        return CalenderStripeView(self.context,
                                  ev, self.__font_size, self.__font,
                                  ViewMeasurement.default(width=ViewSize.MATCH_PARENT, margin_bottom=4),
                                  is_split=self.__is_split, is_square=self.__is_square)

    def get_font(self):
        """
        The font family of the summary and time label
        :return: file path to the current font
        """
        return self.__font

    def set_font(self, font: ImageFont.ImageFont):
        """
        The font family of the summary and time label. May lead to a full redraw
        :param font: path to the desired font file. Only be a TrueTypeFont is acceptable
        """
        for view in self.get_children():
            if type(view) is TextView:
                view.set_font(font)

    def refresh(self):
        """
        Signal the event provider again and redraw
        """
        self.clear()
        events = self.__provider.get_events()

        if len(events) > 0:
            self.add_views(*[self.__get_view(ev) for ev in events])
        else:
            self.add_view(
                TextView(
                    self.context,
                    text='No upcoming events',
                    font_size=self.__font_size,
                    font=self.__font,
                    align_horizontal=ViewAlignmentHorizontal.CENTER,
                    align_vertical=ViewAlignmentVertical.CENTER,
                    prefer=ViewMeasurement.default(size=ViewSize.MATCH_PARENT, margin=4)
                )
            )

        self.invalidate()


class SquareDateView(Group):
    """
    A view that can display a small rectangle which indicates the date
    """

    def __init__(self, context,
                 prefer: ViewMeasurement = ViewMeasurement.default(),
                 font: str = TextView.default_font,
                 weekday_font_size: int = 30,
                 day_font_size: int = 100,
                 month_font_size: int = 20,
                 current_week_font_size: int = 25,
                 first_week: str | None = None,
                 width: int = 200):
        """
        :param context: The context that the view is in
        :param prefer: The preferred measurement of the view
        :param font: The font of the text
        :param weekday_font_size: The font size of the weekday
        :param day_font_size: The font size of the day
        :param month_font_size: The font size of the month
        :param current_week_font_size: The font size of the current week
        :param first_week: String representation of any day in the first week this semester. Format: yyyy-mm-dd
        :param width: The width of the view
        """
        super().__init__(context, prefer)
        self.__font = font
        self.__width = width
        self.__day_font_size = day_font_size
        self.__weekday_font_size = weekday_font_size
        self.__month_font_size = month_font_size
        self.__current_week_font_size = current_week_font_size
        if first_week is not None:
            self.__first_week = datetime.datetime.strptime(first_week, "%Y-%m-%d")
            self.__first_week -= datetime.timedelta(self.__first_week.weekday())
        else:
            self.__first_week = None
        self.__add_view()

    def measure(self):
        self.__base_surface.actual_measurement = ViewMeasurement.default(
            size=self.actual_measurement.size,
        )
        self.__header.actual_measurement = ViewMeasurement.default(
            width=self.actual_measurement.size[0],
            height=self.__header.content_size()[1],
            position=(0, 10)
        )

        self.__weekday_textview.actual_measurement = ViewMeasurement.default(
            width=self.actual_measurement.size[0],
            height=self.__weekday_textview.content_size()[1],
            position=(0, self.actual_measurement.size[1] - self.__weekday_textview.content_size()[1] - 10)
        )

        self.__date_textview.actual_measurement = ViewMeasurement.default(
            position=(0, self.__header.actual_measurement.position[1] + self.__header.actual_measurement.size[1]),
            width=self.actual_measurement.size[0],
            height=self.actual_measurement.size[1] - self.__header.actual_measurement.size[1] -
                   self.__weekday_textview.actual_measurement.size[1] - 20
        )

    def content_size(self) -> Tuple[float, float]:
        bounds = [0, 0]
        for child in self.get_children():
            if child.content_size()[0] > bounds[0]:
                bounds[0] = child.content_size()[0]
            bounds[1] += child.content_size()[1]
        return bounds[0], bounds[1] + 20

    def __add_view(self):
        self.__base_surface = Surface(
            context=self.context,
            fill=self.context.acc_color
        )

        self.__date_textview = TextView(
            context=self.context,
            text=lambda: datetime.datetime.now().strftime('%d'),
            font=self.__font,
            font_size=self.__day_font_size,
            fill=self.context.bg_color,
            align_horizontal=ViewAlignmentHorizontal.CENTER,
            align_vertical=ViewAlignmentVertical.CENTER,
        )

        self.__weekday_textview = TextView(
            context=self.context,
            text=lambda: datetime.datetime.now().strftime('%a'),
            font=self.__font,
            font_size=self.__weekday_font_size,
            fill=self.context.bg_color,
            align_horizontal=ViewAlignmentHorizontal.CENTER,
        )

        self.__header = Group(context=self.context, prefer=ViewMeasurement.default(width=ViewSize.MATCH_PARENT))
        month_textview = TextView(
            context=self.context,
            text=lambda: datetime.datetime.now().strftime('%b'),
            font=self.__font,
            font_size=self.__month_font_size,
            fill=self.context.bg_color,
            align_horizontal=ViewAlignmentHorizontal.CENTER,
            align_vertical=ViewAlignmentVertical.TOP,
            prefer=ViewMeasurement.default(width=ViewSize.MATCH_PARENT)
        )

        self.__header.add_view(month_textview)
        if self.__first_week is not None:
            def get_week_offset():
                return f'{(datetime.datetime.now() - self.__first_week).days // 7} '

            current_week_textview = TextView(
                context=self.context,
                text=get_week_offset,
                font=self.__font,
                font_size=self.__current_week_font_size,
                fill=self.context.bg_color,
                align_horizontal=ViewAlignmentHorizontal.RIGHT,
                align_vertical=ViewAlignmentVertical.TOP,
                prefer=ViewMeasurement.default(width=ViewSize.MATCH_PARENT)
            )
            self.__header.add_view(current_week_textview)

        self.add_views(
            self.__base_surface,
            self.__header,
            self.__date_textview,
            self.__weekday_textview
        )
