# flake8: noqa
import nbconvert
import nbgrader

if __name__ == "__main__":
    raise RuntimeError("This is a configuration file. It contains no runnable code.")

c = get_config()

c.ExportPlugin.config = "feedback_config.json"

tex_exts = [
    "aux",
    "bbl",
    "bcf",
    "blg",
    "fdb_latexmk",
    "fls",
    "log",
    "nav",
    "out",
    "run.xml",
    "snm",
    "synctex.gz",
    "tex",
    "toc",
    "vrb",
]

c.CourseDirectory.ignore = [
    "*data_generation*.ipynb",
    "timestamp.txt",
    "_*",
    ".ipynb_checkpoints",
    "*.pyc",
    "__pycache__",
    ".pytest_cache",
    "__init__.py",
    "feedback",
    "*.png",
    "*.svg",
    "*.jpg",
    "^tikz/*",
    "*.tex",
    *map("*.".__add__, tex_exts),
]
c.CourseDirectory.notebook_id = "[!_]*"

c.GenerateAssignment.preprocessors = [
    nbgrader.preprocessors.LockCells,
    nbgrader.preprocessors.ClearSolutions,
    nbgrader.preprocessors.ClearOutput,
    nbgrader.preprocessors.CheckCellMetadata,
    nbgrader.preprocessors.ComputeChecksums,
    nbgrader.preprocessors.SaveCells,
    nbgrader.preprocessors.ClearHiddenTests,
    nbgrader.preprocessors.ClearMarkScheme,
    nbgrader.preprocessors.ComputeChecksums,
    nbgrader.preprocessors.CheckCellMetadata,
]

c.GenerateFeedback.preprocessors = [
    nbgrader.preprocessors.GetGrades,
    nbconvert.preprocessors.CSSHTMLHeaderPreprocessor,
    nbgrader.preprocessors.ClearHiddenTests,
    nbgrader.preprocessors.Execute,
    nbgrader.preprocessors.LimitOutput(max_lines=10),
]
