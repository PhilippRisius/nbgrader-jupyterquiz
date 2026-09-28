"""Nbgrader preprocessor that converts markdown quiz regions into interactive quizzes."""

import html
import itertools
import json
import pprint
from textwrap import dedent

import nbformat.v4
from nbconvert.exporters.exporter import ResourcesDict
from nbformat.notebooknode import NotebookNode
from nbgrader import utils
from nbgrader.preprocessors.base import NbGraderPreprocessor
from traitlets import Bool, Unicode

from nbgrader_jupyterquiz.grader import encode, parse


class CreateQuiz(NbGraderPreprocessor):
    """
    Convert markdown quiz regions to interactive jupyterquiz cells.

    Register in ``nbgrader_config.py`` at the **front** of the
    ``GenerateAssignment`` preprocessor list so that auto-generated
    autograder cells are picked up by ``SaveCells`` (into the gradebook)
    and ``ClearHiddenTests`` (to strip the grading body from the release)::

        c.GenerateAssignment.preprocessors.insert(0, "nbgrader_jupyterquiz.CreateQuiz")

    Appending instead of inserting (``.append(...)``) will cause autograde
    to fail because our cells wouldn't be in the gradebook and their
    checksums wouldn't match the release.
    """

    begin_quiz_delimiter = Unicode(
        "#### Quiz",
        help="The delimiter marking the beginning of quiz source.",
    ).tag(config=True)

    end_quiz_delimiter = Unicode(
        "#### End Quiz",
        help="The delimiter marking the end of quiz source.",
    ).tag(config=True)

    enforce_metadata = Bool(
        True,
        help=dedent(
            """
            Whether to raise an error if cells containing quiz regions are not
            marked as 'Manually Graded Task' cells.  Only disable this if you
            are using nbgrader generate_assignment without the full grading pipeline.
            """
        ),
    ).tag(config=True)

    auto_generate_tests = Bool(
        True,
        help=dedent(
            """
            Whether to auto-generate autograder-cell content when the host
            task cell carries an nbgrader ``grade_id``.

            When ``True`` (the default), each generated ``display_quiz``
            code cell also becomes the nbgrader-tracked graded cell: its
            source carries a ``### BEGIN HIDDEN TESTS`` block that embeds
            the answer key and calls
            :func:`~nbgrader_jupyterquiz.grade_quiz` — the block is
            stripped from the release by ``ClearHiddenTests`` and restored
            at autograde time by ``OverwriteCells``.  A bare
            ``_result.score`` expression at the end of the cell feeds
            nbgrader's partial-credit scoring
            (``utils.determine_grade``).  The task cell's own ``points``
            field is left untouched so it can still be manually graded
            alongside the auto-graded quiz score.

            Disable to opt out of auto-grading and keep ``display_quiz``
            as a plain (non-graded) code cell; in that mode instructors
            author their own autograded test cells.
            """
        ),
    ).tag(config=True)

    # Current notebook name, quiz-cell counter and claimed data filenames
    # (all reset per notebook in preprocess).
    name = ""
    quiz_cell_counter = itertools.count()
    # ``filename=`` files claimed so far, keyed by (assignment, path) and
    # mapped to the claiming notebook.  Notebooks of one assignment share
    # a release directory, so two of them must not write the same file.
    _claimed_files: dict[tuple[str, str], str] | None = None

    def preprocess(self, nb: NotebookNode, resources: ResourcesDict) -> tuple[NotebookNode, ResourcesDict]:
        """
        Process all markdown cells in the notebook, expanding quiz regions.

        Parameters
        ----------
        nb : NotebookNode
            Source notebook.
        resources : ResourcesDict
            Nbgrader resources dict (provides ``unique_key``).  Quiz data
            files requested with ``filename=`` are added to
            ``resources["outputs"]`` so nbconvert writes them next to the
            output notebook.

        Returns
        -------
        NotebookNode, ResourcesDict
            Modified notebook with quiz cells appended after each quiz region.
        """
        nb, resources = super().preprocess(nb, resources)
        if "celltoolbar" in nb.metadata:
            del nb.metadata["celltoolbar"]

        self.name = resources["unique_key"]
        self.quiz_cell_counter = itertools.count()
        self._filenames: set[str] = set()
        self._assignment = str((resources.get("nbgrader") or {}).get("assignment", ""))
        if self._claimed_files is None:
            self._claimed_files = {}
        # Re-processing a notebook (e.g. ``--force``) releases its old claims.
        for key in [k for k, owner in self._claimed_files.items() if owner == self.name]:
            del self._claimed_files[key]
        new_cells: list[NotebookNode] = []

        for cell in nb["cells"]:
            # Quizzes live in markdown task cells; a code cell with a
            # ``#### Quiz ...`` comment is not a quiz.
            if cell.cell_type != "markdown":
                new_cells.append(cell)
                continue
            quizzes, cell_contents = self._safe_parse_cell(cell)
            quiz_cells: list[NotebookNode] = []
            if quizzes:
                quiz_cells = self._handle_quiz_cell(cell, quizzes, cell_contents, resources)
            cell.source = "\n".join(cell_contents)
            new_cells.append(cell)
            new_cells.extend(quiz_cells)

        nb["cells"] = new_cells
        return nb, resources

    def _safe_parse_cell(self, cell: NotebookNode) -> tuple[list[parse.Quiz], list[str]]:
        """
        Parse a cell, surfacing parse errors and warnings through nbgrader's log.

        Any non-fatal warnings raised by the parser (e.g. MC with 0 or 1
        correct answers, ignored lines or options) are re-emitted
        through ``self.log.warning`` so they surface in nbgrader's UI
        output.  Fatal parse errors on task cells are logged through
        ``self.log.error`` before being re-raised.  On other cells they
        raise when ``enforce_metadata`` is on (a quiz outside a task
        cell is an error either way, and leaving it unparsed would ship
        its answer key to students) and are logged as a warning
        otherwise.

        Parameters
        ----------
        cell : NotebookNode
            Cell to parse.

        Returns
        -------
        quizzes : list[parse.Quiz]
            Empty when the cell has no quiz region or cannot be parsed and
            is not a task cell.
        cell_contents : list[str]
            Remaining lines of the cell with quiz regions stripped.

        Raises
        ------
        parse.ParseError
            If a task cell's quiz region is malformed.
        RuntimeError
            If a non-task cell's quiz region is malformed and
            ``enforce_metadata`` is on.
        """
        grade_id = cell.metadata.get("nbgrader", {}).get("grade_id")
        cell_ref = f"cell {grade_id!r}" if grade_id else "cell (unnamed)"
        try:
            quizzes, cell_contents = parse.parse_cell(
                cell.source,
                self.begin_quiz_delimiter,
                self.end_quiz_delimiter,
            )
        except parse.ParseError as err:
            if utils.is_task(cell):
                self.log.error("Quiz parse error in %s: %s", cell_ref, err)
                raise
            if self.enforce_metadata:
                raise RuntimeError(
                    f"Malformed quiz region in a non-task cell ({err}); please mark all quiz cells as 'Manually Graded Task'."
                ) from err
            self.log.warning(
                "Quiz region in non-task %s could not be parsed and is left unchanged (metadata enforcement is off): %s",
                cell_ref,
                err,
            )
            return [], cell.source.split("\n")
        for quiz in quizzes:
            for warning in quiz.warnings:
                self.log.warning("%s: %s", cell_ref, warning)
        return quizzes, cell_contents

    def _handle_quiz_cell(
        self,
        cell: NotebookNode,
        quizzes: list[parse.Quiz],
        cell_contents: list[str],
        resources: ResourcesDict,
    ) -> list[NotebookNode]:
        """
        Transform one quiz-bearing cell: validate, promote, emit code cells.

        Parameters
        ----------
        cell : NotebookNode
            The source task cell being transformed.
        quizzes : list[parse.Quiz]
            Quiz regions parsed from the cell.
        cell_contents : list[str]
            Mutable list of remaining cell lines; inline/hidden span
            content is appended to this list in place.
        resources : ResourcesDict
            Nbgrader resources dict; receives ``filename=`` quiz data
            under ``resources["outputs"]``.

        Returns
        -------
        list[NotebookNode]
            Generated code cells to append after the task cell.
        """
        if not utils.is_task(cell) and self.enforce_metadata:
            raise RuntimeError("Quiz detected in a non-task cell; please mark all quiz cells as 'Manually Graded Task'.")
        quiz_cell_idx = next(self.quiz_cell_counter)
        grade_id = cell.metadata.get("nbgrader", {}).get("grade_id")
        # Host-cell graded toggle: the per-quiz ``graded`` option can
        # further opt individual quizzes out.  Task-cell ``points`` are
        # left untouched — they remain for manual grading of whatever
        # isn't the auto-graded quiz (prose, code, etc.).  The generated
        # auto-graded cell carries its own ``points`` (sum of
        # per-question weights).
        host_graded = bool(grade_id and self.auto_generate_tests)

        if grade_id:
            self._propagate_hide_correctness(quizzes)

        quiz_cells: list[NotebookNode] = []
        for quiz_idx, quiz in enumerate(quizzes):
            tag = f"{quiz_cell_idx}.{quiz_idx}"
            source_ref = self._inject_quiz_content(quiz, tag, cell_contents, resources)
            quiz_graded = host_graded and quiz.options.get("graded") is not False
            quiz_cells.append(
                self._build_quiz_code_cell(
                    quiz,
                    quiz_idx,
                    source_ref,
                    grade_id,
                    quiz_graded,
                    len(quizzes),
                )
            )
        return quiz_cells

    @staticmethod
    def _propagate_hide_correctness(quizzes: list[parse.Quiz]) -> None:
        """
        Auto-enable hide-correctness for graded quizzes unless opted out.

        Mutates each quiz's options and answer/question dicts in place:
        sets ``hide_correctness=True`` and stamps ``hide: true`` onto
        every MC/many-choice answer and numeric question.  Skips quizzes
        where the instructor explicitly wrote ``hide_correctness=false``
        or ``graded=false`` (an ungraded quiz reveals correctness like
        any self-checking quiz).  Instructors can still force
        hide-correctness on an ungraded quiz by writing
        ``hide_correctness=true`` explicitly.

        Parameters
        ----------
        quizzes : list[parse.Quiz]
            Quiz regions belonging to a graded task cell.
        """
        for quiz in quizzes:
            if quiz.options.get("hide_correctness") is False:
                continue  # instructor opted out
            if quiz.options.get("graded") is False and quiz.options.get("hide_correctness") is not True:
                continue  # ungraded: default to visible correctness
            quiz.options["hide_correctness"] = True
            for question in quiz.questions:
                if question["type"] in ("multiple_choice", "many_choice"):
                    for answer in question["answers"]:
                        answer.setdefault("hide", True)
                elif question["type"] in ("numeric", "string"):
                    question.setdefault("hide", True)

    def _inject_quiz_content(
        self,
        quiz: parse.Quiz,
        tag: str,
        cell_contents: list[str],
        resources: ResourcesDict,
    ) -> str:
        """
        Embed the quiz JSON in the host cell, or emit it as a data file.

        Returns the reference ``display_quiz`` should use to locate the
        question data at render time.

        Parameters
        ----------
        quiz : parse.Quiz
            Parsed quiz region.
        tag : str
            ``"<cell_idx>.<quiz_idx>"`` tag used as the span id suffix.
        cell_contents : list[str]
            Mutable cell source lines; the hidden or visible span is
            appended unless ``filename=`` is set.
        resources : ResourcesDict
            Nbgrader resources dict; with ``filename=``, the JSON is
            stored under ``resources["outputs"][filename]`` so that
            nbconvert's ``FilesWriter`` writes it next to the output
            (release) notebook, where the student's ``display_quiz``
            call looks for it.

        Returns
        -------
        str
            First argument for ``display_quiz``: the filename when
            ``filename=`` is set, else ``"#<name>:<tag>"``.
        """
        display_questions = parse.redact_answer_key(quiz.questions) if quiz.options.get("hide_correctness") else quiz.questions
        questions_json = json.dumps(display_questions)

        if filename := quiz.options.get("filename"):
            # The loader splices the file into JavaScript as a literal,
            # so it must be plain JSON: ``encoded`` does not apply.
            if filename in self._filenames:
                raise RuntimeError(f"Quiz data file {filename!r} is used by more than one quiz in notebook {self.name!r}.")
            key = (self._assignment, filename)
            owner = self._claimed_files.setdefault(key, self.name)
            if owner != self.name:
                raise RuntimeError(f"Quiz data file {filename!r} of notebook {self.name!r} is already written by notebook {owner!r}.")
            self._filenames.add(filename)
            resources.setdefault("outputs", {})[filename] = questions_json.encode("utf-8")
            return filename

        if quiz.options.get("encoded"):
            questions_json = encode.to_base64(questions_json)
        # ``tex2jax_ignore`` / ``mathjax_ignore`` keep MathJax from
        # rewriting ``$...$`` inside the JSON payload.  Backslashes are
        # doubled so JupyterLab's markdown renderer (which consumes
        # ``\X`` punctuation escapes before the JS reads
        # ``element.innerHTML``) leaves JSON's own ``\"`` / ``\\`` /
        # ``\uXXXX`` escapes intact for ``JSON.parse``.  No-op for the
        # default ``encoded=true`` path — base64 has no backslashes.
        span_json = questions_json.replace("\\", "\\\\").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        span_id = html.escape(f"{self.name}:{tag}", quote=True)
        style = ' style="display:none"' if quiz.options.get("hidden") else ""
        cell_contents.append(f'<span{style} id="{span_id}" class="{span_id} tex2jax_ignore mathjax_ignore">{span_json}</span>')
        return f"#{self.name}:{tag}"

    def _build_quiz_code_cell(  # noqa: PLR0913
        self,
        quiz: parse.Quiz,
        quiz_idx: int,
        source_ref: str,
        grade_id: str | None,
        graded_mode: bool,
        region_count: int,
    ) -> NotebookNode:
        """
        Build one code cell — graded (hidden tests + answer key) or plain.

        Every cell carries its own ``display_quiz`` import so it renders
        even when run on its own (e.g. after a kernel restart).

        Parameters
        ----------
        quiz : parse.Quiz
            Parsed quiz region for this cell.
        quiz_idx : int
            0-based index of this quiz within its host task cell
            (used to uniquify the graded cell's grade_id when multiple
            quizzes share one task cell).
        source_ref : str
            First argument to ``display_quiz``: filename or
            ``"#<name>:<tag>"``.
        grade_id : str or None
            Task cell's nbgrader grade_id, if any.
        graded_mode : bool
            ``True`` when this cell should be the nbgrader-tracked
            graded cell (hidden-tests block + answer key embedded).
        region_count : int
            Number of quiz regions in the host task cell.  When > 1,
            the generated ``cell_grade_id`` is uniquified per region.

        Returns
        -------
        NotebookNode
            New code cell with ``["remove-input"]`` tag and, in graded
            mode, nbgrader metadata so ``SaveCells`` registers it.
        """
        # JSON string syntax is valid Python and keeps the double quotes
        # of earlier releases; unlike raw interpolation it survives
        # quotes or backslashes in notebook names and filenames.
        ref = json.dumps(source_ref, ensure_ascii=False)
        imp = "from nbgrader_jupyterquiz.display import display_quiz\n"
        if not graded_mode:
            return nbformat.v4.new_code_cell(
                source=f"{imp}display_quiz({ref}, grade_id={grade_id!r})",
                metadata={"tags": ["remove-input"]},
            )

        cell_grade_id = f"{grade_id}-autograded"
        if region_count > 1:
            cell_grade_id = f"{cell_grade_id}-{quiz_idx}"

        questions_literal = pprint.pformat(
            quiz.questions,
            width=80,
            indent=2,
            sort_dicts=False,
        )
        # Bare ``_result.score`` at the end of the hidden block is
        # what nbgrader's ``determine_grade()`` reads: the cell's
        # execute_result becomes the partial-credit score.
        cell_source = (
            f"{imp}"
            f"display_quiz({ref}, grade_id={cell_grade_id!r})\n"
            "### BEGIN HIDDEN TESTS\n"
            "from nbgrader_jupyterquiz import grade_quiz\n"
            f"_questions = {questions_literal}\n"
            f"_result = grade_quiz({cell_grade_id!r}, questions=_questions)\n"
            "_result.display_review()\n"
            'print(f"Score: {_result.score}/{_result.max_score}")\n'
            "_result.score\n"
            "### END HIDDEN TESTS\n"
        )
        cell_metadata = {
            "tags": ["remove-input"],
            "nbgrader": {
                "cell_type": "code",
                "grade": True,
                "grade_id": cell_grade_id,
                "locked": True,
                "points": sum(q.get("points", 1) for q in quiz.questions),
                "schema_version": 3,
                "solution": False,
                "task": False,
            },
        }
        return nbformat.v4.new_code_cell(source=cell_source, metadata=cell_metadata)

    def preprocess_cell(self, cell: NotebookNode, resources: ResourcesDict, _index: int) -> tuple[NotebookNode, ResourcesDict]:
        """
        No-op — all processing happens in :meth:`preprocess`.

        Parameters
        ----------
        cell : NotebookNode
            Current cell.
        resources : ResourcesDict
            Nbgrader resources dict.
        _index : int
            Cell index (unused).

        Returns
        -------
        NotebookNode, ResourcesDict
            Cell unchanged.
        """
        return cell, resources
