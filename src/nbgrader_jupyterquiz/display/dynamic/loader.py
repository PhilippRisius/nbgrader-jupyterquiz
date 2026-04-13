"""Load question data from a list, file, URL, or DOM element reference."""

import json
import pathlib
import sys
import urllib.request


try:
    from pyodide.http import open_url
except ImportError:
    try:
        from pyodide import open_url
    except ImportError:
        open_url = None


def load_questions_script(ref, div_id):
    """
    Build a JavaScript prefix that loads questions into ``questions{div_id}``.

    Parameters
    ----------
    ref : list or str
        Question list, DOM element id (starting with ``#``), HTTP URL, or
        local file path.
    div_id : str
        Unique identifier for the quiz container div.

    Returns
    -------
    script : str
        JavaScript code that defines the ``questions{div_id}`` variable.
    static : bool
        ``True`` when questions are embedded; ``False`` for async URL loading.
    url : str
        The source URL when ``static`` is ``False``, otherwise empty string.
    """
    script = ""
    static = True
    url = ""

    if isinstance(ref, list):
        script = f"var questions{div_id}=" + json.dumps(ref)
    elif isinstance(ref, str):
        if ref.startswith("#"):
            element_id = ref[1:]
            script = (
                f'var element = document.getElementById("{element_id}");\n'
                f'if (element == null) {{ console.log("ID failed, trying class"); '
                f'var elems = document.getElementsByClassName("{element_id}"); '
                f"element = elems[0]; }}\n"
                f'if (element == null) {{ throw new Error("Cannot find element {element_id}"); }}\n'
                f"var questions{div_id};\n"
                f"try {{ questions{div_id} = JSON.parse(window.atob(element.innerHTML)); }} "
                f'catch(err) {{ console.log("Parsing error, using raw innerHTML"); '
                f"questions{div_id} = JSON.parse(element.innerHTML); }}\n"
                f"console.log(questions{div_id});"
            )
        elif ref.lower().startswith("http"):
            script = f"var questions{div_id}="
            url = ref
            if sys.platform == "emscripten" and open_url:
                text = open_url(url).read()
                script += text
            else:
                with urllib.request.urlopen(url) as response:
                    for line in response:
                        script += line.decode("utf-8")
            static = False
        else:
            script = f"var questions{div_id}="
            with pathlib.Path(ref).open() as f:
                for line in f:
                    script += line
            static = True
    else:
        raise TypeError("ref must be a list, URL string, or file path string")

    script += ";\n\nif (typeof Question === 'undefined') {\n"
    return script, static, url
