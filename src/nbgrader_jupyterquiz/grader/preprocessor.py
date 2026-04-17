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
            Whether to auto-generate an autograded test cell after each quiz
            task cell.  When ``True`` (the default) and the host task cell has
            an nbgrader ``grade_id``, the preprocessor emits a test cell that
            calls ``grade_quiz(grade_id)`` and asserts a pass, and forces the
            task cell's ``points`` to 0 to avoid double-counting with the
            auto-grade score.  Disable if you prefer to author test cells
            manually.
            """
        ),
    ).tag(config=True)

    # Current notebook name and quiz-cell counter (reset per notebook via preprocess).
    name = ""
    quiz_cell_counter = itertools.count()

    def preprocess(self, nb: NotebookNode, resources: ResourcesDict) -> tuple[NotebookNode, ResourcesDict]:  # noqa: C901
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

        imported = False
        self.name = resources["unique_key"]
        new_cells = []

        for cell in nb["cells"]:
            try:
                quizzes, cell_contents = parse.parse_cell(cell.source, self.begin_quiz_delimiter, self.end_quiz_delimiter)
            except parse.ParseError:
                cell_contents = cell.source.split("\n")
                if utils.is_task(cell):
                    raise
                else:
                    quizzes = []
                    if not self.enforce_metadata:
                        self.log.warning("Cell could not be parsed, but metadata enforcement is off.")

            quiz_cells = []
            if quizzes:
                quiz_cell_idx = next(self.quiz_cell_counter)

                if not utils.is_task(cell) and self.enforce_metadata:
                    raise RuntimeError("Quiz detected in a non-task cell; please mark all quiz cells as 'Manually Graded Task'.")

                grade_id = cell.metadata.get("nbgrader", {}).get("grade_id")

                # Graded quizzes must hide correctness feedback so students
                # can't guess their way to the right answer.  When the host
                # task cell has an nbgrader grade_id and the instructor hasn't
                # explicitly opted out by setting ``hide_correctness=false``,
                # propagate ``hide: true`` onto every answer (MC / many-choice
                # answers consume it per-answer; numeric reads it per-question
                # via ``question.hide`` — set below).
                if grade_id:
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

                # When the task cell is graded, the auto-generated cell
                # becomes the nbgrader-tracked graded cell itself (not a
                # sibling).  Its source holds the display_quiz call (visible
                # to students in the release) plus a hidden-tests block that
                # embeds the answer key and invokes grade_quiz(...).  The
                # release strips the hidden block via ClearHiddenTests; the
                # autograder reinstates it via OverwriteCells.  Points
                # migrate off the task cell to avoid double-counting.
                graded_mode = bool(grade_id and self.auto_generate_tests)
                if graded_mode:
                    # Task-cell points are always replaced with zero so the
                    # manually-graded channel doesn't double-count.  Each
                    # generated graded cell is worth ``len(questions)``
                    # points — one per question — and partial credit falls
                    # out naturally from ``_result.score`` being an int
                    # between 0 and max_score (see the hidden test body).
                    cell.metadata.setdefault("nbgrader", {})["points"] = 0

                for quiz_idx, quiz in enumerate(quizzes):
                    tag = f"{quiz_cell_idx}.{quiz_idx}"
                    questions_json = json.dumps(quiz.questions)

                    if quiz.options.get("encoded"):
                        questions_json = encode.to_base64(questions_json)

                    if quiz.options.get("inline"):
                        if quiz.options.get("hidden"):
                            cell_contents.append(
                                f'<span style="display:none" id="{self.name}:{tag}" class="{self.name}:{tag}">{questions_json}</span>'
                            )
                        else:
                            cell_contents.append(f"{tag}={questions_json}")

                    if filename := quiz.options.get("filename"):
                        try:
                            with pathlib.Path(filename).open("w") as f:
                                f.writelines(questions_json)
                        except OSError:
                            self.log.error("Cannot open for writing: %s", filename)
                        source = filename
                    else:
                        source = f"#{self.name}"

                    imp = "" if imported else "from nbgrader_jupyterquiz.display import display_quiz\n"
                    imported = True

                    if graded_mode:
                        cell_grade_id = f"{grade_id}-autograded"
                        if len(quizzes) > 1:
                            cell_grade_id = f"{cell_grade_id}-{quiz_idx}"
                        questions_literal = pprint.pformat(
                            quiz.questions,
                            width=80,
                            indent=2,
                            sort_dicts=False,
                        )
                        # The bare ``_result.score`` at the end of the
                        # hidden block is what nbgrader's determine_grade()
                        # reads: the execute_result of the cell becomes the
                        # partial-credit score (0..len(questions)).
                        cell_source = (
                            f"{imp}"
                            f'display_quiz("{source}:{tag}", grade_id={cell_grade_id!r})\n'
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
                                # Cell max_points = sum of per-question points;
                                # each question's ``points`` field defaults to 1.
                                "points": sum(q.get("points", 1) for q in quiz.questions),
                                "schema_version": 3,
                                "solution": False,
                                "task": False,
                            },
                        }
                    else:
                        cell_source = f'{imp}display_quiz("{source}:{tag}", grade_id={grade_id!r})'
                        cell_metadata = {"tags": ["remove-input"]}

                    quiz_cells.append(
                        nbformat.v4.new_code_cell(
                            source=cell_source,
                            metadata=cell_metadata,
                        )
                    )

            cell.source = "\n".join(cell_contents)
            new_cells.append(cell)
            new_cells.extend(quiz_cells)

        nb["cells"] = new_cells
        return nb, resources

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
