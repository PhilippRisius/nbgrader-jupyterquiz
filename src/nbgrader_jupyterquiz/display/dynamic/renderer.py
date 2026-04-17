"""Render HTML, CSS, and JavaScript components of the quiz display."""

import importlib.resources
from string import Template


# Assets live in the display/ subpackage (styles.css, js/)
_ASSETS_PACKAGE = "nbgrader_jupyterquiz.display"


def render_div(div_id, shuffle_questions, shuffle_answers, preserve_responses, num, max_width, border_radius, question_alignment, grade_id=None):
    """
    Build the HTML container div with data attributes and inline style.

    Parameters
    ----------
    div_id : str
        Unique identifier for the container.
    shuffle_questions : bool
        Whether to shuffle question order.
    shuffle_answers : bool
        Whether to shuffle answer order.
    preserve_responses : bool
        Whether to keep responses visible after answering.
    num : int
        Maximum number of questions to display.
    max_width : int
        Maximum width in pixels.
    border_radius : int
        CSS border-radius in pixels.
    question_alignment : str
        CSS text-align value.
    grade_id : str, optional
        Nbgrader ``grade_id`` of the host task cell.  When provided,
        emitted as ``data-grade-id`` so the JS recorder persists
        responses to the sidecar file; omitted when ``None``.

    Returns
    -------
    str
        Opening ``<div>`` tag with all required data attributes.
    """
    preserve_json = "true" if preserve_responses else "false"
    grade_attr = f' data-grade-id="{grade_id}"' if grade_id else ""
    return (
        f'<div id="{div_id}" '
        f'data-shufflequestions="{shuffle_questions}" '
        f'data-shuffleanswers="{shuffle_answers}" '
        f'data-preserveresponses="{preserve_json}" '
        f'data-numquestions="{num}" '
        f'data-maxwidth="{max_width}"'
        f"{grade_attr} "
        f'style="border-radius: {border_radius}px; text-align: {question_alignment}">'
    )


def build_styles(div_id, color_dict):
    """
    Build the ``<style>`` block with CSS variables and shared styles.

    Parameters
    ----------
    div_id : str
        Unique identifier for the container (used for CSS scoping).
    color_dict : dict
        Mapping of CSS variable names to colour values.

    Returns
    -------
    str
        Complete ``<style>`` tag.
    """
    styles = "<style>\n"
    styles += f"#{div_id} " + "{\n"
    for var, color in color_dict.items():
        styles += f"   {var}: {color};\n"
    styles += "}\n\n"
    css_path = importlib.resources.files(_ASSETS_PACKAGE).joinpath("styles.css")
    styles += css_path.read_bytes().decode("utf-8")
    styles += "</style>"
    return styles


def build_script(prefix_script, static, url, div_id, load_js):
    """
    Combine the loading prefix, static JS files, and suffix template.

    Parameters
    ----------
    prefix_script : str
        JavaScript that defines the questions variable.
    static : bool
        ``True`` when questions are embedded (use static suffix template).
    url : str
        Source URL for async loading when ``static`` is ``False``.
    div_id : str
        Unique identifier for the container div.
    load_js : bool
        Whether to inline the quiz JavaScript source.

    Returns
    -------
    str
        Complete JavaScript block (without surrounding ``<script>`` tags).
    """
    script = prefix_script

    if load_js:
        js_dir = importlib.resources.files(_ASSETS_PACKAGE).joinpath("js")
        for js_file in sorted(js_dir.iterdir(), key=lambda x: x.name):
            if js_file.name.endswith(".js"):
                script += js_file.read_bytes().decode("utf-8")

    if static:
        tpl_path = importlib.resources.files(_ASSETS_PACKAGE).joinpath("js/static_suffix.js.tpl")
        tpl = tpl_path.read_text()
        script += Template(tpl).substitute(div_id=div_id)
    else:
        tpl_path = importlib.resources.files(_ASSETS_PACKAGE).joinpath("js/async_suffix.js.tpl")
        tpl = tpl_path.read_text()
        script += Template(tpl).substitute(url=url, div_id=div_id)

    script += "\n}\n"
    return script
