import pathlib


GENERAL = {
    ("-v", "--verbose"): {
        "action": "count",
        "dest": "verbosity",
        "default": 0,
        "help": "verbose output (repeat for increased verbosity)",
    },
    ("-q", "--quiet"): {
        "action": "store_const",
        "const": -1,
        "default": 0,
        "dest": "verbosity",
        "help": "quiet output (show errors only)",
    },
}

REPORT_CREATION = {
    ("--csv_file", "-c"): {
        "required": True,
        "type": pathlib.Path,
        "default": pathlib.Path(),
        "dest": "csv_file",
        "action": "store",
        "help": "csv file for reading grading results",
    },
    ("--report-file", "-r"): {
        "required": True,
        "type": pathlib.Path,
        "dest": "report_file",
        "default": pathlib.Path(),
        "action": "store",
        "help": "Report file to write the result of exercise grading to.",
    },
    ("--name", "-n"): {
        "required": False,
        "type": str,
        "default": "",
        "dest": "name",
        "action": "store",
        "help": "report title",
    },
    ("--geometry", "-g"): {
        "required": False,
        "type": str,
        "dest": "geometry",
        "default": "a4paper_portrait",
        "action": "store",
        "help": "paper format for output report.",
    },
    ("--scheme", "-s"): {
        "required": False,
        "type": pathlib.Path,
        "dest": "grading_scheme",
        "default": pathlib.Path(),
        "action": "store",
        "help": "Markdown file with grading scheme to include in the report verbatim.",
    },
    ("--level", "-l"): {
        "required": False,
        "type": int,
        "dest": "aggregation_level",
        "default": 2,
        "action": "store",
        "help": "aggregation level for plotting point distribution",
    },
}
