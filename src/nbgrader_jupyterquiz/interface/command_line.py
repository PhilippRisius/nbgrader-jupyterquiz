import argparse
import logging
import os

import argcomplete

import nbgrader_jupyterquiz.report_creation.create_report as create_report
from nbgrader_jupyterquiz.interface.cli_args import GENERAL, REPORT_CREATION


logger = logging.getLogger(__name__)


def parse_command_line_args(prog, cli_args):
    parser = argparse.ArgumentParser(prog=prog, description="")

    for args, kwargs in (cli_args | GENERAL).items():
        parser.add_argument(*args, **kwargs)

    argcomplete.autocomplete(parser)
    cli_args = parser.parse_args()
    cli_args.loglevel = setup_logging(cli_args.verbosity)
    return cli_args


def setup_logging(verbosity):
    base_loglevel = int(os.getenv("LOGLEVEL", 30))
    verbosity = min(verbosity, 2)
    loglevel = base_loglevel - (verbosity * 10)
    logging.basicConfig(level=loglevel, format="%(message)s")

    return loglevel


def main():
    cmd_args = parse_command_line_args(prog="report_creation", cli_args=REPORT_CREATION)
    create_report.main(cmd_args)


if __name__ == "__main__":
    main()
