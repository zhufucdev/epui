from ui import *

CANVAS_SIZE = (800, 480)


def main():
    image = Image.new('L', CANVAS_SIZE, 255)
    draw = ImageDraw.Draw(image)
    context = Context(draw, CANVAS_SIZE)
    vgroup = VGroup(context)
    vgroup.add_views(
        View(context)
    )
    context.root_group.add_view(vgroup)
    context.redraw_once()
    image.show('test')


if __name__ == '__main__':
    main()
