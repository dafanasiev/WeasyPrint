"""
    weasyprint.svg.text
    -------------------

    Draw text.

"""

from math import cos, inf, radians, sin

from .bounding_box import EMPTY_BOUNDING_BOX, extend_bounding_box
from .utils import normalize, size


class TextBox:
    """Dummy text box used to draw text."""
    def __init__(self, pango_layout, style):
        self.pango_layout = pango_layout
        self.style = style


def text(svg, node, font_size):
    """Draw text node."""
    from ..css.properties import INITIAL_VALUES
    from ..draw import draw_emojis, draw_first_line
    from ..text.line_break import split_first_line

    # TODO: use real computed values
    style = INITIAL_VALUES.copy()
    style['font_family'] = [
        font.strip('"\'') for font in
        node.get('font-family', 'sans-serif').split(',')]
    style['font_style'] = node.get('font-style', 'normal')
    style['font_weight'] = node.get('font-weight', 400)
    style['font_size'] = font_size
    if style['font_weight'] == 'normal':
        style['font_weight'] = 400
    elif style['font_weight'] == 'bold':
        style['font_weight'] = 700
    else:
        try:
            style['font_weight'] = int(style['font_weight'])
        except ValueError:
            style['font_weight'] = 400

    layout, _, _, width, height, _ = split_first_line(
        node.text, style, svg.context, inf, 0)
    # TODO: get real values
    x_bearing, y_bearing = 0, 0

    # Get rotations and translations
    x, y, dx, dy, rotate = [], [], [], [], [0]
    if 'x' in node.attrib:
        x = [size(i, font_size, svg.inner_width)
             for i in normalize(node.attrib['x']).strip().split(' ')]
    if 'y' in node.attrib:
        y = [size(i, font_size, svg.inner_height)
             for i in normalize(node.attrib['y']).strip().split(' ')]
    if 'dx' in node.attrib:
        dx = [size(i, font_size, svg.inner_width)
              for i in normalize(node.attrib['dx']).strip().split(' ')]
    if 'dy' in node.attrib:
        dy = [size(i, font_size, svg.inner_height)
              for i in normalize(node.attrib['dy']).strip().split(' ')]
    if 'rotate' in node.attrib:
        rotate = [radians(float(i)) if i else 0
                  for i in normalize(node.attrib['rotate']).strip().split(' ')]
    last_r = rotate[-1]
    letters_positions = [
        ([pl.pop(0) if pl else None for pl in (x, y, dx, dy, rotate)], char)
        for char in node.text]

    # Align text box horizontally
    x_align = 0
    letter_spacing = svg.length(node.get('letter-spacing'), font_size)
    text_anchor = node.get('text-anchor')
    # TODO: use real values
    ascent, descent = font_size * .8, font_size * .2
    if text_anchor == 'middle':
        x_align = - (width / 2. + x_bearing)
        if letter_spacing and node.text:
            x_align -= (len(node.text) - 1) * letter_spacing / 2
    elif text_anchor == 'end':
        x_align = - (width + x_bearing)
        if letter_spacing and node.text:
            x_align -= (len(node.text) - 1) * letter_spacing

    # Align text box vertically
    # TODO: This is a hack. Other baseline alignment tags are not supported.
    # See https://www.w3.org/TR/SVG2/text.html#TextPropertiesSVG
    y_align = 0
    display_anchor = node.get('display-anchor')
    alignment_baseline = node.get(
        'dominant-baseline', node.get('alignment-baseline'))
    if display_anchor == 'middle':
        y_align = -height / 2 - y_bearing
    elif display_anchor == 'top':
        y_align = -y_bearing
    elif display_anchor == 'bottom':
        y_align = -height - y_bearing
    elif alignment_baseline in ('central', 'middle'):
        # TODO: This is wrong, we use font top-to-bottom
        y_align = (ascent + descent) / 2 - descent
    elif alignment_baseline in (
            'text-before-edge', 'before_edge', 'top', 'hanging', 'text-top'):
        y_align = ascent
    elif alignment_baseline in (
            'text-after-edge', 'after_edge', 'bottom', 'text-bottom'):
        y_align = -descent

    # Set bounding box
    bounding_box = EMPTY_BOUNDING_BOX

    # Return early when there’s no text
    if not node.text:
        x = x[0] if x else svg.cursor_position[0]
        y = y[0] if y else svg.cursor_position[1]
        dx = dx[0] if dx else 0
        dy = dy[0] if dy else 0
        svg.cursor_position = (x + dx, y + dy)
        return

    svg.stream.begin_text()
    emoji_lines = []

    # Draw letters
    for i, ((x, y, dx, dy, r), letter) in enumerate(letters_positions):
        if x:
            svg.cursor_d_position[0] = 0
        if y:
            svg.cursor_d_position[1] = 0
        svg.cursor_d_position[0] += dx or 0
        svg.cursor_d_position[1] += dy or 0
        layout, _, _, width, height, _ = split_first_line(
            letter, style, svg.context, inf, 0)
        svg.stream.push_state()
        x = svg.cursor_position[0] if x is None else x
        y = svg.cursor_position[1] if y is None else y
        if i:
            x += letter_spacing
        x_position = x + svg.cursor_d_position[0] + x_align
        y_position = y + svg.cursor_d_position[1] + y_align
        svg.stream.move_to(x_position, y_position)
        cursor_position = x + width, y
        angle = last_r if r is None else r
        if angle:
            svg.stream.transform(e=x_position, f=y_position)
            svg.stream.transform(
                a=cos(angle), b=sin(angle), c=-sin(angle), d=cos(angle))
            svg.stream.transform(e=-x_position, f=-y_position)
        points = (
            (cursor_position[0] + x_align +
             svg.cursor_d_position[0],
             cursor_position[1] + y_align +
             svg.cursor_d_position[1]),
            (cursor_position[0] + x_align + width +
             svg.cursor_d_position[0],
             cursor_position[1] + y_align + height +
             svg.cursor_d_position[1]))
        bounding_box = extend_bounding_box(bounding_box, points)

        layout.reactivate(style)
        svg.fill_stroke(node, font_size, text=True)
        emojis = draw_first_line(
            svg.stream, TextBox(layout, style), 'none', 'none',
            x_position, y_position)
        emoji_lines.append((font_size, x, y, emojis))
        svg.stream.pop_state()
        svg.cursor_position = cursor_position

    svg.stream.end_text()

    for font_size, x, y, emojis in emoji_lines:
        draw_emojis(svg.stream, font_size, x, y, emojis)
