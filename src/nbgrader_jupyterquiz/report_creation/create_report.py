"""Main module for report creation from database entries"""

import logging
import pathlib

from nbgrader_jupyterquiz.report_creation import plotting, read_csv_results, report_writer


logger = logging.getLogger(__name__)


def main(cli_args):
    """Parse grading results into a pdf report via pandoc."""
    if cli_args.csv_file.suffix != ".csv":
        logger.critical("cannot read in from data source other than csv!")
        exit(1)

    logger.info("Reading grades from %s.", cli_args.csv_file)
    df_scores = read_csv_results.read_grades_from_csv(cli_args.csv_file)

    if "total_reached" not in df_scores.columns:
        df_scores["total_reached"] = df_scores.sum(axis=1)

    plot_file = pathlib.Path(str(cli_args.report_file) + "_plot.pdf")
    logger.info("Plotting points distribution to %s.", plot_file)
    plotting.plot_task_points_distribution(
        df_scores,
        filename=plot_file,
        aggregation_level=plotting.AggregationLevel(cli_args.aggregation_level),
    )

    md_file = f"{cli_args.report_file.resolve()}.md"
    logger.info("Writing markdown report to %s", md_file)
    report_writer.write_markdown_report(
        df_scores.rename(columns=report_writer.rename_columns(df_scores)),
        md_file,
        cli_args.name,
        taskptdistr_img=plot_file,
        grading_scheme=cli_args.grading_scheme,
        geometry=cli_args.geometry,
    )

    pdf_file = f"{cli_args.report_file.resolve()}.pdf"
    logger.info("Converting markdown file to %s", pdf_file)
    report_writer.write_pdf_report(md_file, pdf_file, template="eisvogel.tex")
