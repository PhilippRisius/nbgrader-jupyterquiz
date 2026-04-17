"""Nbgrader preprocessor that converts markdown quiz regions into interactive quizzes."""

import itertools
import json
import pathlib
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
            are using nbgrader assign without the full grading pipeline.
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
            (``utils.determine_grade``).  The task cell's ``points`` field
            is forced to 0 so the manually-graded channel does not
            double-count against the autograded score.

            Disable to opt out of auto-grading and keep ``display_quiz``
            as a plain (non-graded) code cell; in that mode instructors
            author their own autograded test cells.
            """
        ),
    ).tag(config=True)

    # Current notebook name and quiz-cell counter (reset per notebook via preprocess).
    name = ""
    quiz_cell_counter = itertools.count()

    def preprocess(self, nb: NotebookNode, resources: ResourcesDict) -> tuple[NotebookNode, ResourcesDict]:
        """
        Process all cells in the notebook, expanding quiz regions.

        Parameters
        ----------
        nb : NotebookNode
            Source notebook.
        resources : ResourcesDict
            Nbgrader resources dict (provides ``unique_key``).

        Returns
        -------
        NotebookNode, ResourcesDict
            Modified notebook with quiz cells appended after each quiz region.
        """
        nb, resources = super().preprocess(nb, resources)
        if "celltoolbar" in nb.metadata:
            del nb.metadata["celltoolbar"]

        self.name = resources["unique_key"]
        new_cells: list[NotebookNode] = []
        imported = False

        for cell in nb["cells"]:
            quizzes, cell_contents = self._safe_parse_cell(cell)
            quiz_cells: list[NotebookNode] = []
            if quizzes:
                quiz_cells, imported = self._handle_quiz_cell(
                    cell,
                    quizzes,
                    cell_contents,
                    imported,
                )
            cell.source = "\n".join(cell_contents)
            new_cells.append(cell)
            new_cells.extend(quiz_cells)

        nb["cells"] = new_cells
        return nb, resources

    def _safe_parse_cell(self, cell: NotebookNode) -> tuple[list[parse.Quiz], list[str]]:
        """
        Parse a cell, reraising ParseErrors on task cells and swallowing elsewhere.

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
        """
        try:
            return parse.parse_cell(cell.source, self.begin_quiz_delimiter, self.end_quiz_delimiter)
        except parse.ParseError:
            if utils.is_task(cell):
                raise
            if not self.enforce_metadata:
                self.log.warning("Cell could not be parsed, but metadata enforcement is off.")
            return [], cell.source.split("\n")

    def _handle_quiz_cell(
        self,
        cell: NotebookNode,
        quizzes: list[parse.Quiz],
        cell_contents: list[str],
        imported: bool,
    ) -> tuple[list[NotebookNode], bool]:
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
        imported : bool
            Whether the ``display_quiz`` import statement has already
            been emitted upstream in this notebook.

        Returns
        -------
        quiz_cells : list[NotebookNode]
            Generated code cells to append after the task cell.
        imported : bool
            Updated flag (``True`` once any quiz cell has been emitted).
        """
        if not utils.is_task(cell) and self.enforce_metadata:
            raise RuntimeError("Quiz detected in a non-task cell; please mark all quiz cells as 'Manually Graded Task'.")
        quiz_cell_idx = next(self.quiz_cell_counter)
        grade_id = cell.metadata.get("nbgrader", {}).get("grade_id")
        graded_mode = bool(grade_id and self.auto_generate_tests)

        if grade_id:
            self._propagate_hide_correctness(quizzes)
        if graded_mode:
            # Task-cell points are zeroed so the manually-graded channel
            # doesn't double-count against the autograded score.
            cell.metadata.setdefault("nbgrader", {})["points"] = 0

        quiz_cells: list[NotebookNode] = []
        for quiz_idx, quiz in enumerate(quizzes):
            tag = f"{quiz_cell_idx}.{quiz_idx}"
            source_ref = self._inject_quiz_content(quiz, tag, cell_contents)
            imp = "" if imported else "from nbgrader_jupyterquiz.display import display_quiz\n"
            imported = True
            quiz_cells.append(
                self._build_quiz_code_cell(
                    quiz,
                    quiz_idx,
                    tag,
                    source_ref,
                    imp,
                    grade_id,
                    graded_mode,
                    len(quizzes),
                )
            )
        return quiz_cells, imported

    @staticmethod
    def _propagate_hide_correctness(quizzes: list[parse.Quiz]) -> None:
        """
        Auto-enable hide-correctness for graded quizzes unless opted out.

        Mutates each quiz's options and answer/question dicts in place:
        sets ``hide_correctness=True`` and stamps ``hide: true`` onto
        every MC/many-choice answer and numeric question.  Skips quizzes
        where the instructor explicitly wrote ``hide_correctness=false``.

        Parameters
        ----------
        quizzes : list[parse.Quiz]
            Quiz regions belonging to a graded task cell.
        """
        for quiz in quizzes:
            if quiz.options.get("hide_correctness") is False:
                continue  # instructor opted out
            quiz.options["hide_correctness"] = True
            for question in quiz.questions:
                if question["type"] in ("multiple_choice", "many_choice"):
                    for answer in question["answers"]:
                        answer.setdefault("hide", True)
                elif question["type"] == "numeric":
                    question.setdefault("hide", True)

    def _inject_quiz_content(
        self,
        quiz: parse.Quiz,
        tag: str,
        cell_contents: list[str],
    ) -> str:
        """
        Render the quiz JSON into the host cell (inline span or filename).

        Returns the selector/path ``display_quiz`` should use to locate
        the question data at render time.

        Parameters
        ----------
        quiz : parse.Quiz
            Parsed quiz region.
        tag : str
            ``"<cell_idx>.<quiz_idx>"`` tag used as both the span id
            suffix and the ``display_quiz`` ref suffix.
        cell_contents : list[str]
            Mutable cell source lines; the hidden/visible span (or the
            plaintext ``tag=...`` variant) is appended when the
            ``inline`` option is set.

        Returns
        -------
        str
            Selector string passed as the first arg to ``display_quiz``:
            the filename when ``filename=`` is set, else ``"#<name>"``.
        """
        questions_json = json.dumps(quiz.questions)
        if quiz.options.get("encoded"):
            questions_json = encode.to_base64(questions_json)

        if quiz.options.get("inline"):
            if quiz.options.get("hidden"):
                cell_contents.append(f'<span style="display:none" id="{self.name}:{tag}" class="{self.name}:{tag}">{questions_json}</span>')
            else:
                cell_contents.append(f"{tag}={questions_json}")

        if filename := quiz.options.get("filename"):
            try:
                with pathlib.Path(filename).open("w") as f:
                    f.writelines(questions_json)
            except OSError:
                self.log.error("Cannot open for writing: %s", filename)
            return filename
        return f"#{self.name}"

    def _build_quiz_code_cell(  # noqa: PLR0913
        self,
        quiz: parse.Quiz,
        quiz_idx: int,
        tag: str,
        source_ref: str,
        imp: str,
        grade_id: str | None,
        graded_mode: bool,
        region_count: int,
    ) -> NotebookNode:
        """
        Build one code cell — graded (hidden tests + answer key) or plain.

        Parameters
        ----------
        quiz : parse.Quiz
            Parsed quiz region for this cell.
        quiz_idx : int
            0-based index of this quiz within its host task cell
            (used to uniquify the graded cell's grade_id when multiple
            quizzes share one task cell).
        tag : str
            ``"<cell_idx>.<quiz_idx>"`` tag used as both the DOM span id
            suffix and the ``display_quiz`` ref suffix.
        source_ref : str
            First argument to ``display_quiz``: filename or ``"#<name>"``.
        imp : str
            Either an empty string or the one-time ``from … import
            display_quiz`` statement to prepend on the first cell.
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
        if not graded_mode:
            return nbformat.v4.new_code_cell(
                source=f'{imp}display_quiz("{source_ref}:{tag}", grade_id={grade_id!r})',
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
            f'display_quiz("{source_ref}:{tag}", grade_id={cell_grade_id!r})\n'
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
