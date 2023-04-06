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

    def date(self):
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


class GoogleCalendarProvider(CalendarProvider):
    """
    A working implementation of CalendarProvider than involves Google Workspace
    """
    def __init__(self, name: str, credentials_file: str, calendar_id: str = 'primary', max_results: int = 10, filter_today: bool = False):
        """
        Creates a GoogleCalendarProvider
        :param name: what to call it
        :param credentials_file: path to the credentials file. To get one, see
        https://developers.google.com/calendar/api/quickstart/python#set_up_your_environment

        :param calendar_id: the calendar id which the owner of the credentials ever created
        :param max_results: how many results at most should the `get_events` function return
        :param filter_today: show only today's event
        """
        self.__calendar_id = calendar_id
        self.__filter_today = filter_today

        scope = ['https://www.googleapis.com/auth/calendar.readonly']
        creds = None
        if cache.exits('gcp_token.json'):
            creds = Credentials.from_authorized_user_file(cache.get_file('gcp_token.json'))
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
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

            if self.__filter_today:
                events_remove = []
                now_day = datetime.datetime.now().timetuple().tm_yday
                for event in events:
                    event_start_day = self.__parse_event(event).get_time().start_time().tm_yday
                    if event_start_day != now_day:
                        events_remove.append(event)
                for event in events_remove:
                    events.remove(event)
        
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
                 prefer: ViewMeasurement = ViewMeasurement.default()):
        """
        Create a CalendarStripeView
        :param context: where the view lives
        :param event: the event to display
        :param font_size: font size of the summary and time
        :param font: file to the desired font family
        :param prefer: preferred layout method
        """
        super().__init__(context, prefer)
        self.__event = event
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
                    radius=10,
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
                 prefer: ViewMeasurement = ViewMeasurement.default()):
        """
        Creates a CalendarView
        :param context: where the view lives in
        :param provider: the event provider
        :param font_size: font size of the summary and time
        :param font: file path to the desired font family. Only be a TrueTypeFont is acceptable
        :param prefer: preferred layout
        """
        self.__provider = provider
        self.__font = font
        self.__font_size = font_size
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
                                  ViewMeasurement.default(width=ViewSize.MATCH_PARENT, margin_bottom=4))

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
