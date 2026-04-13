"""Tools to read results from manual grading from csv file."""

import logging

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)

ID_COLUMN = "Kennung"


class GradingFormattingError(Exception):
    """Exception to be raised when formatting of csv file is not as expected."""

    def __init__(self, message):
        super().__init__(message)


class GradingValueError(Exception):
    """Exception to be raised in case of missing/invalid values in csv file."""

    def __init__(self, message):
        super().__init__(message)


def _check_column_names(df: pd.DataFrame) -> None:
    """
    Check if the names of the columns in the CSV file have the expected format.

    - First column is expected to be labelled ID_COLUMN
    - Last column is expected to be labelled "Summe"
    - A homework assignment can have tasks 1 ... N.
    - Each of the tasks can have a number of subtasks 1 ... M.
    - The columns of the CSV file are expected to have the results for each subtask
      to be contained in a column with aa label following the scheme

      T1.1 T1.2 ... TN.1 TN.2 ...
    """

    def is_valid_label(cname):
        """Check if a label for columns with results for subtasks has a valid naming scheme."""
        return cname.replace(".", "").removeprefix("T").isnumeric()

    column_names = df.columns

    if column_names[0] != ID_COLUMN:
        logger.info("%s", __file__)
        msg = f"Label of first column is not '{ID_COLUMN}'"
        logger.error(msg)
        raise GradingFormattingError(msg)

    if not all(is_valid_label(cname) for cname in column_names[1:]):
        msg = """Some columns with results for subtasks are not following the
                 required naming scheme."""
        logger.error(msg)
        raise GradingFormattingError(msg)


def _check_reference_results(df: pd.DataFrame) -> None:
    """DataFrame must contain an entry 'reachable' in the 'Hash' column."""
    has_reference_results = np.any(df[ID_COLUMN].isin(["reachable"]))
    if not has_reference_results:
        msg = "Reference results are missing in the DataFrame."
        logger.error(msg)
        raise GradingValueError(msg)


def read_grades_from_csv(csv_file):
    """Read manually graded exercises from a csv file."""
    # The delimiter in the csv file is always assumed to be a comma.
    logger.info("Import content of %s into Pandas DataFrame.", csv_file)
    df = pd.read_csv(csv_file, delimiter=",")

    # Perform some checks
    # _check_column_names(df)
    # _check_reference_results(df)  # 'reachable' row must be present

    return df.set_index(ID_COLUMN)
