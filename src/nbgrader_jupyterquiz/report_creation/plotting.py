"""Plot results from grading."""

import logging
import pathlib
from enum import Enum

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt


logger = logging.getLogger(__name__)


class AggregationLevel(Enum):
    """Level of aggregation for plotting."""

    Exercise = 1
    Task = 2
    Subtask = 3
    Test = 4


def _aggregate_scores_to_level(
    scores: pd.DataFrame,
    max_aggregation_level: AggregationLevel = AggregationLevel.Task,
    separator: str = ".",
):
    """
    Aggregate columns in DataFrame by column prefixes.

    Expects the format 'Ta.b.c.d', where a, b, c, d are single characters identifying subtasks.
    """
    aggregate_scores = {}
    for aggregation_level in range(max_aggregation_level.value):
        logging.debug("Aggregating scores at level %s", aggregation_level)

        columns_left = scores.columns.copy()
        df_agg = pd.DataFrame(index=scores.index)
        df_indices = pd.DataFrame(index=pd.Index(["start", "end"]))
        end = -1
        while len(columns_left) > 0:
            logging.debug("left to aggregate: %s", columns_left)
            start = end + 1
            prefix = separator.join((columns_left[0] + separator).split(separator, maxsplit=aggregation_level)[:-1])
            col_name = prefix or "total"
            logging.debug("Aggregating columns with %s", prefix)

            matching_columns = columns_left[(columns_left == prefix) | columns_left.str.startswith(f"{prefix}." if prefix else "")]
            logging.debug("Aggregating %s", matching_columns)

            df_agg[col_name] = np.zeros(len(scores.index), dtype=int)
            for column in matching_columns:
                columns_left = columns_left.drop(column)
                df_agg[col_name] += scores[column].fillna(0 if len(matching_columns) > 1 else np.nan)
                end += 1

            df_indices[col_name] = start, end
            aggregate_scores[aggregation_level] = (
                df_indices,
                df_agg,
            )  # .dropna(how='all'))

    return aggregate_scores


def _plot(df, colname, ax_info, with_legend=False, orientation="vertical", max_pts=0):
    """Helper function to plot columns from DataFrame."""
    idx, ax = ax_info
    ax.set_title(f"Aufgabe {colname.lstrip('T')}")
    # Tick and grid settings
    ax.set_yticks(np.arange(0, max_pts + 1, 2))
    ax.minorticks_on()

    unique, counts = np.unique(df.drop("reachable")[colname], return_counts=True)
    mean, median = df.drop("reachable")[colname].agg(["mean", "median"])

    if orientation == "horizontal":
        # create a horizontal bar plot, and adjust axis labels.
        ax.barh(unique, counts, align="center")  # , width='0.35')
        if idx == 0:
            ax.set_ylabel("Erreichte Punkte")
        ax.set_ylim(-0.5, max_pts + 0.5)
        ax.set_yticks(np.arange(0, max_pts + 1, max([1, max_pts // 3])))
        ax.set_xlabel("Anzahl")
        x_min, x_max = ax.get_xlim()
        ax.set_xticks(np.arange(0, x_max + 1, max([1, x_max // 3])))

        ax.plot(
            [x_min, x_max],
            [mean, mean],
            color="darkred",
            linestyle="--",
            linewidth=1.5,
            label="mean",
        )
        ax.plot(
            [x_min, x_max],
            [median, median],
            color="darkorange",
            linestyle="--",
            linewidth=1.5,
            label="median",
        )

    elif orientation == "vertical":
        # create a vertical bar plot, and adjust axis labels accordingly.
        ax.bar(unique, counts, align="center", width=0.35)
        ax.set_title("Gesamt")
        ax.minorticks_on()
        ax.set_ylabel("Anzahl")
        ax.set_xlabel("Erreichte Punkte")
        ax.set_xlim(-0.5, max_pts + 0.5)
        ax.set_xticks(np.arange(0, max_pts + 1, max([1, max_pts // 3])))
        ymin, ymax = ax.get_ylim()
        ax.set_yticks(np.arange(0, ymax, 2))
        for q, label, color in [
            (mean, "mean", "darkred"),
            (median, "median", "darkorange"),
        ]:
            ax.plot(
                [q, q],
                [ymin, ymax],
                color=color,
                linestyle="--",
                linewidth=1.5,
                label=label,
            )

    if with_legend:
        ax.legend()


def plot_task_points_distribution(
    df_scores,
    filename,
    tmpdir: pathlib.Path = pathlib.Path(),
    aggregation_level: AggregationLevel = AggregationLevel.Task,
):
    """Figures containing statistics on the results for the current exercise."""
    columns = list(filter(lambda x: x.replace(".", "").isnumeric(), df_scores.columns))

    fig = plt.figure(figsize=(20, 2.5 * aggregation_level.value))
    gs = fig.add_gridspec(nrows=aggregation_level.value, ncols=len(columns), hspace=0.5)

    # Plot the points from the single tasks
    logger.debug("Aggregating scores to level %s", aggregation_level)
    aggregated_scores = _aggregate_scores_to_level(df_scores[columns], aggregation_level)
    logger.debug("%s", aggregated_scores)

    for row in range(aggregation_level.value):
        df_ind, df_agg = aggregated_scores[row]
        for idx, column in enumerate(df_agg.columns):
            max_pts = df_agg.loc["reachable"].iat[idx]
            start, end = df_ind[column]
            ax = fig.add_subplot(gs[aggregation_level.value - row - 1, slice(start, end + 1)])
            _plot(
                df_agg,
                column,
                (idx, ax),
                max_pts=max_pts,
                orientation="vertical" if row == 0 else "horizontal",
                with_legend=row == 0,
            )

    plt.savefig(tmpdir / filename, bbox_inches="tight")
