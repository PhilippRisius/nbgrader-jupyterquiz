/*
 * Graded-quiz response recorder.
 *
 * When a quiz container has data-grade-id set (via
 * display_quiz(..., grade_id="...")) and the host is backed by a
 * jupyter_server, this module persists student responses to a
 * responses.json sidecar file in the same directory as the notebook.
 * The autograder helper reads that sidecar in a hidden autograded
 * test cell.
 *
 * No-op when data-grade-id is absent (non-nbgrader callers) or when
 * the notebook directory cannot be discovered from the URL (e.g.,
 * VS Code's Jupyter extension, which is not supported).
 */

/* Extract [baseUrl, dir] from window.location.pathname.  Handles
 *   /lab/tree/<dir>/<file>.ipynb                (JupyterLab 4)
 *   /lab/workspaces/<ws>/tree/...               (JupyterLab workspaces)
 *   /user/<user>/lab/tree/...                   (JupyterHub multi-user)
 *   /doc/tree/...                               (Notebook 7 doc mode)
 *   /notebooks/...                              (Notebook 7 / classic)
 * Returns null if the URL does not look like a Jupyter notebook route. */
function _nbgjqDiscoverLocation() {
    var m = window.location.pathname.match(
        /^(\/(?:user\/[^/]+\/)?)(?:(?:lab|doc)\/(?:workspaces\/[^/]+\/)?tree|notebooks)\/(.+\/)[^/]+\.ipynb(?:[#?].*)?$/
    );
    if (!m) return null;
    return [m[1], decodeURIComponent(m[2])];
}

/* Read the XSRF token from cookies for authenticated same-origin writes. */
function _nbgjqReadXsrfToken() {
    var cookies = document.cookie.split('; ');
    for (var i = 0; i < cookies.length; i++) {
        if (cookies[i].indexOf('_xsrf=') === 0) {
            return cookies[i].substring('_xsrf='.length);
        }
    }
    return '';
}

/* Persist a single response to responses.json next to the notebook.
 * Graceful no-op if gradeId is falsy or notebook location cannot be
 * resolved.  All errors are logged and swallowed; this function must
 * not throw.
 *
 * payload shape is type-tagged (schema_version 1):
 *   { type: "multiple_choice", selected: "Paris" }
 *   { type: "many_choice",     selected: ["list", "dict"] }
 *   { type: "numeric",         raw: "1/2", parsed: 0.5 }
 *   { type: "string",          value: "hello" } */
async function recordResponse(gradeId, qnum, payload) {
    if (!gradeId) return;
    var loc = _nbgjqDiscoverLocation();
    if (!loc) {
        console.warn('nbgrader_jupyterquiz: cannot discover notebook path; response not saved.');
        return;
    }
    var baseUrl = loc[0];
    var dir = loc[1];
    var apiUrl = baseUrl + 'api/contents/' + dir + 'responses.json';

    try {
        var body = { schema_version: 1, responses: {} };
        var getResp = await fetch(apiUrl + '?content=1', { credentials: 'same-origin' });
        if (getResp.ok) {
            var model = await getResp.json();
            try {
                var parsed = JSON.parse(model.content);
                if (parsed && typeof parsed === 'object' && parsed.responses) {
                    body = parsed;
                }
            } catch (e) {
                console.warn('nbgrader_jupyterquiz: existing responses.json is malformed; overwriting.');
            }
        } else if (getResp.status !== 404) {
            console.warn('nbgrader_jupyterquiz: GET ' + apiUrl + ' returned ' + getResp.status + '; response not saved.');
            return;
        }

        if (!body.responses[gradeId]) body.responses[gradeId] = {};
        body.responses[gradeId][String(qnum)] = payload;

        var putResp = await fetch(apiUrl, {
            method: 'PUT',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-XSRFToken': _nbgjqReadXsrfToken(),
            },
            body: JSON.stringify({
                type: 'file',
                format: 'text',
                content: JSON.stringify(body, null, 2),
            }),
        });
        if (!putResp.ok) {
            console.warn('nbgrader_jupyterquiz: PUT ' + apiUrl + ' returned ' + putResp.status + '; response not saved.');
        }
    } catch (e) {
        console.warn('nbgrader_jupyterquiz: unexpected error while saving response:', e);
    }
}
