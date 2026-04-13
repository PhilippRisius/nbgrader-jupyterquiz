"""Generate PDF/markdown report with results of exercise grading."""

import logging
import os
import pathlib
from datetime import datetime

import pypandoc


logger = logging.getLogger(__name__)

HTML_STATUS_TEMPLATE_NAME = "task_status_template.html"
HTML_TABLE_TEMPLATE_NAME = "report_template.html"
CSS_STYLE_FILE = "./table_style.css"


class PaperFormat:
    a4paper_landscape = 'geometry: "paperwidth=297mm,paperheight=210mm,top=20mm,bottom=20mm,right=20mm,left=20mm"'
    a4paper_portrait = 'geometry: "paperwidth=210mm,paperheight=297mm,top=20mm,bottom=20mm,right=20mm,left=20mm"'
    a3paper_landscape = 'geometry: "paperwidth=420mm,paperheight=297mm,top=20mm,bottom=20mm,right=20mm,left=20mm"'


COURSE_TITLE = os.getenv("COURSE_TITLE")
if COURSE_TITLE is None:
    logger.warning('Course title could not be found.\nSet environment variable "COURSE_TITLE" to have non-empty headers.')

REPORT_AUTHOR = os.getenv("REPORT_AUTHOR")
if REPORT_AUTHOR is None:
    logger.warning('Report author could not be found.\nSet environment variable "REPORT_AUTHOR" to have non-empty author in reports.')


def rename_columns(df):
    return {cname: f"Aufgabe {idx + 1}" for idx, cname in enumerate(df.columns) if "task" in cname} | {"total_reached": "Gesamt"}


def __rename_columns(old_columns, col1_name="Hash"):
    """Helper function to rename columns to german names."""
    new_columns = [f"Aufgabe {idx + 1}" for idx in range(len(old_columns) - 1)] + ["Gesamt"]
    return {
        **{"index": col1_name},
        **{old_name: new_name for old_name, new_name in zip(old_columns, new_columns, strict=False)},
    }


def _pandoc_header(header_line: str, date, geometry=None):
    header = "---\n"
    header += 'title: "' + header_line + '"\n'
    header += f"author: [{REPORT_AUTHOR}]\n"
    header += f'date: "{date.strftime("%Y-%m-%d")}"\n'
    header += f'header-center: "{COURSE_TITLE}"\n'
    if geometry is not None:
        header += getattr(PaperFormat, geometry) + "\n"
    header += "fontsize: 12 \nfontfamilyoptions:\n - sf\n"
    header += "...\n\n"
    return header


def write_markdown_report(df, filename, exercise_name, **kwargs):
    """Write markdown report file."""
    if "Kennung" in df.columns:
        df["Kennung"] = "`" + df["Kennung"] + "`"

    today = datetime.today()

    header_line = exercise_name

    with pathlib.Path(filename).open("w") as f:
        logger.debug("Writing header section")
        f.write(_pandoc_header(header_line, today, kwargs.get("geometry")))
        f.write(f"# {COURSE_TITLE}\n")
        f.write("## Aufgabenbewertung: " + header_line + "\n\n")
        f.write(df.sort_index().to_markdown())
        f.write("\n\n\\newpage\n\n")
        if kwargs.get("grading_scheme", pathlib.Path()).is_file():
            logger.debug("including grading scheme from %s.", kwargs["grading_scheme"])
            f.write("## Bewertungsschema:\n")
            with pathlib.Path(kwargs["grading_scheme"]).open() as scheme:
                f.write("\n".join(list(scheme.readlines())))
            f.write(r"\vfill")
        if kwargs.get("taskptdistr_img"):
            f.write("\n\n## Statistiken:\n")
            logger.debug("including statistics from %s.", kwargs["taskptdistr_img"])
            f.write(f"\n\n![Statistiken]({kwargs['taskptdistr_img']})")


def _results_weeks_to_markdown(df, filename, info):
    """Write results for multiple weeks to markdown."""
    if "Hash" in df.columns:
        df["Hash"] = "`" + df["Hash"] + "`"

    today = datetime.today()

    header_line = "Gesamtübersicht Übungspunkte"

    with pathlib.Path(filename).open("w") as f:
        f.write(_pandoc_header(header_line, today, info.get("geometry")))
        f.write(f"# {COURSE_TITLE}\n")
        if all(
            map(
                lambda s: info.get(s, None) is not None,
                ("name", "surname", "hash_string"),
            )
        ):
            f.write(f"## Hausaufgabenbewertung für {info['name']} {info['surname']} ({info['hash_string']})\n")
        f.write(df.to_markdown(index=True))


def write_pdf_report(markdown_filename, pdf_filename, **kwargs):
    logger.info("Converting markdown to pdf with pandoc")

    extra_args = ["-V", "lang=de"]
    for key, value in kwargs.items():
        extra_args += [f"--{key}", value]

    pypandoc.convert_file(
        markdown_filename,
        "pdf",
        format="md",
        outputfile=pdf_filename,
        extra_args=extra_args,
    )


def write_reports_weeks(df, filename, **kwargs):
    """Write report files in PDF or markdown format."""
    if filename.endswith(".pdf"):
        raise NotImplementedError()
    elif filename.endswith(".md"):
        _results_weeks_to_markdown(df, filename, kwargs)
