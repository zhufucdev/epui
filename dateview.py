from datetime import datetime
import ui

class SquareDateView(ui.Group):
    """
    The class that can display a small rectangle which indicates the date
    """
    def __init__(self, context, prefer, font,
                  weekday_font_size: int = 30,
                    day_font_size:int = 100,
                    month_font_size:int = 20,
                    current_week_font_size:int = 25,
                    current_week_offset:int = None,
                    width:int = 200):
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

    def __base_surface(self) -> ui.Surface:
        return ui.Surface(
            context=self.context,
            fill=100,
            prefer=ui.ViewMeasurement.default(
                width=ui.ViewSize.MATCH_PARENT,
                height=ui.ViewSize.MATCH_PARENT
            )
        )

    def __date_textview(self) -> ui.TextView:
        return ui.TextView(
            context=self.context,
            text=datetime.now().strftime('%d'),
            font=self.__font,
            font_size=self.__day_font_size,
            fill=255,
            align_horizontal=ui.ViewAlignmentHorizontal.CENTER,
            align_vertical=ui.ViewAlignmentVertical.CENTER,
            prefer=ui.ViewMeasurement.default(
                width=ui.ViewSize.MATCH_PARENT,
                height=ui.ViewSize.WRAP_CONTENT
            )
        )

    def __month_textview(self) -> ui.TextView:
        return ui.TextView(
            context=self.context,
            text=datetime.now().strftime('%b'),
            font=self.__font,
            font_size=self.__month_font_size,
            fill=255,
            align_horizontal=ui.ViewAlignmentHorizontal.CENTER,
            align_vertical=ui.ViewAlignmentVertical.TOP,
            prefer=ui.ViewMeasurement.default(
                width=ui.ViewSize.MATCH_PARENT,
                height=ui.ViewSize.WRAP_CONTENT
            )
        )

    def __weekday_textview(self) -> ui.TextView:
        return ui.TextView(
            context=self.context,
            text=datetime.now().strftime('%a') + '\n ',
            font=self.__font,
            font_size=self.__weekday_font_size,
            fill=255,
            align_horizontal=ui.ViewAlignmentHorizontal.CENTER,
            align_vertical=ui.ViewAlignmentVertical.BOTTOM,
            prefer=ui.ViewMeasurement.default(
                width=ui.ViewSize.MATCH_PARENT,
                height=ui.ViewSize.MATCH_PARENT
            )
        )

    def __current_week_textview(self) -> ui.TextView:
        if self.__current_week_offset is None:
            return None
        curr_week = int(datetime.now().strftime('%W'))
        return ui.TextView(
            context=self.context,
            text=str(curr_week + self.__current_week_offset) + ' ',
            font=self.__font,
            font_size=self.__current_week_font_size,
            fill=255,
            align_horizontal=ui.ViewAlignmentHorizontal.RIGHT,
            align_vertical=ui.ViewAlignmentVertical.TOP,
            prefer=ui.ViewMeasurement.default(
                width=ui.ViewSize.MATCH_PARENT,
                height=ui.ViewSize.WRAP_CONTENT
            )
        )

    def __add_view(self):
        group = ui.Group(self.context, prefer=ui.ViewMeasurement.default(
            width=self.__width,
            height=ui.ViewSize.MATCH_PARENT
        ))
        group.add_views(
            self.__base_surface(),
            self.__date_textview(),
            self.__weekday_textview(),
            self.__month_textview(),
        )
        if self.__current_week_textview() is not None:
            group.add_view(self.__current_week_textview())
        self.add_view(group)
    