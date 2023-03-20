from ui import *

CANVAS_SIZE = (800, 480)


def main():
    image = Image.new('L', CANVAS_SIZE, color=255)
    draw = ImageDraw.Draw(image)
    context = Context(draw, CANVAS_SIZE)
    vgroup = VGroup(context,
                    prefer=ViewMeasurement.default(width=ViewSize.MATCH_PARENT))
    vgroup.add_views(
        View(context, prefer=ViewMeasurement(size=0.5)),
        View(context,
             prefer=ViewMeasurement.default(
                 margin_top=10,
                 margin_bottom=10,
                 width=ViewSize.MATCH_PARENT
             )),
        View(context,
             prefer=ViewMeasurement.default(
                 margin_left=10,
                 margin_right=10,
                 width=ViewSize.MATCH_PARENT
             )),
    )
    context.root_group.add_view(vgroup)
    context.redraw_once()
    image.show('test')


if __name__ == '__main__':
    main()
