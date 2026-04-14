"""Capture student responses from a rendered quiz container."""

import random
import string

from IPython.display import HTML, Javascript, display


def capture_responses(prev_div_id):
    """
    Attempt to capture and display responses from a previous quiz container.

    Parameters
    ----------
    prev_div_id : str
        The ``div_id`` of the quiz container whose responses should be captured.
    """
    div_id = "".join(random.choice(string.ascii_letters) for _ in range(12))

    mydiv = f'<div id="{div_id}"></div>'
    javascript = f"""
{{
  var prev = {prev_div_id};
  var container = document.getElementById("{div_id}");
  var responses = prev.querySelector('.JCResponses');
  if (responses) {{
    var respStr = responses.dataset.responses;
    container.setAttribute('data-responses', respStr);
    var iDiv = document.createElement('div');
    iDiv.id = 'responses' + '{div_id}';
    iDiv.innerText = respStr;
    container.appendChild(iDiv);
  }} else {{
    container.innerText = 'No Responses Found';
  }}
}}
"""
    display(HTML(mydiv))
    display(Javascript(javascript))
