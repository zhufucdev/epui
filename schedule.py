import datetime
import logging
import time as pytime
from enum import Enum
from typing import *

import googleapiclient.discovery as gcp
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

import cache
import util
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

    def get_span(self) -> int:
        return self.__span

    def start_date(self):
        return self.__date


class TwoStepTimeSpan(EventTimeSpan):
    def __init__(self, start: pytime.struct_time, end: pytime.struct_time):
        self.__start = start
        self.__end = end
        super().__init__(False)

    def start_time(self):
        return self.__start

    def end_time(self):
        return self.__end


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
        return type(other) == Event and other


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

    def __init__(self, name: str, credentials_file: str, calendar_id: str = 'primary', max_results: int = 10):
        """
        Creates a GoogleCalendarProvider
        :param name: what to call it
        :param credentials_file: path to the credentials file. To get one, see
        https://developers.google.com/calendar/api/quickstart/python#set_up_your_environment

        :param calendar_id: the calendar id which the owner of the credentials ever created
        :param max_results: how many results at most should the `get_events` function return
        """
        self.__calendar_id = calendar_id

        scope = ['https://www.googleapis.com/auth/calendar.readonly']
        creds = None
        if cache.exits('gcp_token.json'):
            creds = Credentials.from_authorized_user_file(cache.get_file('gcp_token.json'))
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scope)
            creds = flow.run_local_server(bind_addr='localhost', port=3891)
            with cache.open_cache('gcp_token.json', 'w') as token:
                token.write(creds.to_json())

        self.__service = gcp.build('calendar', 'v3', credentials=creds)
        super().__init__(name, max_results)

    @staticmethod
    def __parse_event(data: Dict[str, Any]) -> Event:
        if 'T' in data['start']['dateTime']:
            full_format = '%Y-%m-%dT%H:%M:%S%z'
            start, end = pytime.strptime(data['start']['dateTime'], full_format), \
                pytime.strptime(data['end']['dateTime'], full_format)
            span = TwoStepTimeSpan(start, end)
        else:
            daily_format = '%Y-%m-%d'
            start, end = pytime.strptime(data['start']['date'], daily_format), \
                pytime.strptime(data['end']['date'], daily_format)
            span = FullDayTimeSpan(date=start, span=(pytime.mktime(end) - pytime.mktime(start)) // 86400)

        return Event(data['summary'], data['location'], span)

    def get_events(self) -> List[Event]:
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
                 is_splited: bool = False, is_square: bool = False):
        """
        Create a CalendarStripeView
        :param context: where the view lives
        :param event: the event to display
        :param font_size: font size of the summary and time
        :param font: file to the desired font family
        :param prefer: preferred layout method
        :param is_splited: whether to split the view into two parts
        :param is_square: whether to make the view square
        """
        super().__init__(context, prefer)
        self.__event = event
        radius = 10
        if is_square:
            radius = 0

        if is_splited:
            self.__name_text_view = TextView(context,
                                             text=self.__get_event_name(),
                                             font_size=font_size,
                                             font=font,
                                             fill=255,
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
                                             fill=255,
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
                        fill=1,
                        prefer=ViewMeasurement.default(size=ViewSize.MATCH_PARENT)),
                self.__name_text_view,
                self.__span_text_view)
        else:
            self.__text_view = TextView(context,
                                        text=self.__get_text(),
                                        font_size=font_size,
                                        font=font,
                                        fill=255,
                                        prefer=ViewMeasurement.default(
                                            margin_top=5,
                                            margin_bottom=2,  # idk why, but it just aligned
                                            margin_left=10,
                                            margin_right=5
                                        ))
            self.add_views(
                Surface(context,
                        radius=radius,
                        fill=1,
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
                 is_splited: bool = False, is_square: bool = False):
        """
        Creates a CalendarView
        :param context: where the view lives in
        :param provider: the event provider
        :param font_size: font size of the summary and time
        :param font: file path to the desired font family. Only be a TrueTypeFont is acceptable
        :param prefer: preferred layout
        :param is_splited: if the view should be splited
        """
        self.__provider = provider
        self.__font = font
        self.__font_size = font_size
        self.__is_splited = is_splited
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
                                  is_splited=self.__is_splited, is_square=self.__is_square)

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
                 current_week_offset: int | None = None,
                 width: int = 200):
        """
        :param context: The context that the view is in
        :param prefer: The preferred measurement of the view
        :param font: The font of the text
        :param weekday_font_size: The font size of the weekday
        :param day_font_size: The font size of the day
        :param month_font_size: The font size of the month
        :param current_week_font_size: The font size of the current week
        :param current_week_offset: The offset of the current week. If not set, will not display the current week
        :param width: The width of the view
        """
        super().__init__(context, prefer)
        self.__font = font
        self.__width = width
        self.__day_font_size = day_font_size
        self.__weekday_font_size = weekday_font_size
        self.__month_font_size = month_font_size
        self.__current_week_font_size = current_week_font_size
        self.__current_week_offset = current_week_offset
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
            fill=100
        )

        self.__date_textview = TextView(
            context=self.context,
            text=datetime.datetime.now().strftime('%d'),
            font=self.__font,
            font_size=self.__day_font_size,
            fill=255,
            align_horizontal=ViewAlignmentHorizontal.CENTER,
            align_vertical=ViewAlignmentVertical.CENTER,
        )

        self.__weekday_textview = TextView(
            context=self.context,
            text=datetime.datetime.now().strftime('%a'),
            font=self.__font,
            font_size=self.__weekday_font_size,
            fill=255,
            align_horizontal=ViewAlignmentHorizontal.CENTER,
        )

        self.__header = Group(context=self.context, prefer=ViewMeasurement.default(width=ViewSize.MATCH_PARENT))
        month_textview = TextView(
            context=self.context,
            text=datetime.datetime.now().strftime('%b'),
            font=self.__font,
            font_size=self.__month_font_size,
            fill=255,
            align_horizontal=ViewAlignmentHorizontal.CENTER,
            align_vertical=ViewAlignmentVertical.TOP,
            prefer=ViewMeasurement.default(width=ViewSize.MATCH_PARENT)
        )

        self.__header.add_view(month_textview)
        if self.__current_week_offset is not None:
            curr_week = int(datetime.datetime.now().strftime('%W'))
            current_week_textview = TextView(
                context=self.context,
                text=str(curr_week + self.__current_week_offset) + ' ',
                font=self.__font,
                font_size=self.__current_week_font_size,
                fill=255,
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
