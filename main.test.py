from ui import *

CANVAS_SIZE = (800, 480)


def main():
    image = Image.new('L', CANVAS_SIZE, color=255)
    draw = ImageDraw.Draw(image)
    context = Context(draw, CANVAS_SIZE)
    vgroup = VGroup(context,
                    alignment=ViewAlignmentHorizontal.RIGHT,
                    prefer=ViewMeasurement.default(width=ViewSize.MATCH_PARENT))
    vgroup.add_views(
        TextView(context,
                 text="What the fuck is going on?",
                 font_size=50,
                 line_align=ViewAlignmentHorizontal.CENTER,
                 align_horizontal=ViewAlignmentHorizontal.CENTER,
                 align_vertical=ViewAlignmentVertical.CENTER,
                 prefer=ViewMeasurement.default(
                     margin_left=10,
                     margin_right=10,
                     size=0.4
                 )),
        View(context,
             prefer=ViewMeasurement(size=0.5)),
        View(context,
             prefer=ViewMeasurement.default(
                 margin=10,
                 width=ViewSize.MATCH_PARENT
             )),
    )
    context.root_group.add_view(vgroup)
    context.redraw_once()
    image.show('test')


if __name__ == '__main__':
    main()
