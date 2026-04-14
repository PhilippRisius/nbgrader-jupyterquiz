"""Nbgrader preprocessor that converts markdown quiz regions into interactive quizzes."""

import itertools
import json
import pathlib
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

    Register in ``nbgrader_config.py`` as a ``GenerateAssignment`` preprocessor::

        c.GenerateAssignment.preprocessors = [
            ...,
            "nbgrader_jupyterquiz.CreateQuiz",
        ]
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

                for quiz_idx, quiz in enumerate(quizzes):
                    tag = f"{quiz_cell_idx}.{quiz_idx}"
                    questions = json.dumps(quiz.questions)

                    if quiz.options.get("encoded"):
                        questions = encode.to_base64(questions)

                    if quiz.options.get("inline"):
                        if quiz.options.get("hidden"):
                            cell_contents.append(f'<span style="display:none" id="{self.name}:{tag}" class="{self.name}:{tag}">{questions}</span>')
                        else:
                            cell_contents.append(f"{tag}={questions}")

                    if filename := quiz.options.get("filename"):
                        try:
                            with pathlib.Path(filename).open("w") as f:
                                f.writelines(questions)
                        except OSError:
                            self.log.error("Cannot open for writing: %s", filename)
                        source = filename
                    else:
                        source = f"#{self.name}"

                    imp = "" if imported else "from nbgrader_jupyterquiz.display import display_quiz\n"
                    imported = True

                    quiz_cells.append(
                        nbformat.v4.new_code_cell(
                            source=f'{imp}display_quiz("{source}:{tag}")',
                            metadata={"tags": ["remove-input"]},
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
