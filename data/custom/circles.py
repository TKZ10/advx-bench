import math
from pathlib import Path

import cairo

WIDTH, HEIGHT = 600, 600

surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
context = cairo.Context(surface)
context.set_source_rgba(0, 0, 0, 0)


def draw_concentric_circles(x, y, max_radius, num_rings):
    for i in range(num_rings):
        radius = max_radius * (i + 1) / num_rings
        context.arc(x, y, radius, 0, 2 * math.pi)

        # blue -> yellow -> red
        color_ratio = i / (num_rings - 1)
        if color_ratio < 0.5:
            # blue -> yellow
            rgb_color = (color_ratio * 2, color_ratio * 2, 1 - color_ratio * 2)
        else:
            # yellow -> red
            rgb_color = (1, 2 - color_ratio * 2, 0)


        context.set_source_rgb(*rgb_color)
        context.set_line_width(1.5)
        context.stroke()


count = 3
num_rings = 15
max_radius = WIDTH / 2 / count

for row in range(count):
    for col in range(count):
        x = (col + 0.5) * WIDTH / count
        y = (row + 0.5) * WIDTH / count
        draw_concentric_circles(x, y, max_radius, num_rings)


surface.write_to_png(Path("data/custom/circles.png"))
