#!/usr/bin/env python3

from dataclasses import dataclass
import pandas as pd
import os
import logging
import subprocess
import argparse
import yaml
import sys
from pathlib import Path
import utils

from fm_tools.fmtoolscatalog import FmToolsCatalog
from fm_tools.competition_participation import Competition, Track
from prepare_tables.utils import competition_from_string, TrackDetails


@dataclass
class Header:
    scale: str
    x_label: str
    y_label: str

    @staticmethod
    def get_header(competition: Competition):
        if competition == Competition.SV_COMP:
            return Header(
                "set logscale y 10",
                "set xlabel 'Cumulative score'",
                "set ylabel 'Min. time in s' offset 3",
            )
        elif competition == Competition.TEST_COMP:
            return Header(
                "unset logscale",
                "set xlabel 'Cumulative score'",
                "set ylabel 'Min. number of test tasks' offset 1",
            )
        raise ValueError("Passed category info does not specify the competition")


@dataclass
class Configuration:
    plot_format: str
    line_width: int
    t_margin: float
    l_margin: float
    r_margin: float
    size_a: tuple
    origin_a: tuple
    size_b: tuple
    origin_b: tuple
    point_interval: int

    @staticmethod
    def get_configuration(file_format):
        if file_format == "pdf":
            return Configuration(
                plot_format='pdfcairo font ",12" size 20cm,10cm',
                line_width=2,
                t_margin=0.5,
                l_margin=9,
                r_margin=1.5,
                size_a=(1, 0.8),
                size_b=(1, 0.18),
                origin_a=(0, 0.18),
                origin_b=(0, 0),
                point_interval=500,
            )
        elif file_format == "png":
            return Configuration(
                plot_format='pngcairo font ",8" size 20cm,10cm',
                line_width=1,
                t_margin=0.5,
                l_margin=7,
                r_margin=0.5,
                size_a=(1, 0.8),
                size_b=(1, 0.2),
                origin_a=(0, 0.2),
                origin_b=(0, 0),
                point_interval=100,
            )
        else:
            return Configuration(
                plot_format='svg font "Helvetica,8" size 800,400',
                line_width=2,
                t_margin=1.2,
                l_margin=10,
                r_margin=2.3,
                size_a=(1, 0.86),
                size_b=(1, 0.14),
                origin_a=(0, 0.150),
                origin_b=(0, 0.01),
                point_interval=300,
            )


def get_tool_name(long_name: str):
    if long_name == "ESBMC+DepthK":
        return "DepthK"
    elif long_name == "SMACK+Corral":
        return "SMACK"
    elif long_name == "CoVeriTeam-Verifier-AlgoSelection":
        return "CVT-AlgoSel"
    elif long_name == "CoVeriTeam-Verifier-ParallelPortfolio":
        return "CVT-ParPort"
    elif long_name == "FuSeBMC_IA":
        return "FuSeBMC-IA"
    return long_name


def line_to_tuple(line):
    parts = line.split("\t")
    assert len(parts) == 2
    return float(parts[0]), float(parts[1])


def generate_plots(
    category_info,
    color_map,
    file_format,
    header,
    config,
    plot_dir,
    results_dir,
    fm_tools_path,
    track_details,
):
    fm_tools_catalog = FmToolsCatalog(fm_tools_path)

    validator = {
        Track.Validation_Correct_1_0: ".correctness-1.0",
        Track.Validation_Violation_1_0: ".violation-1.0",
        Track.Validation_Correct_2_0: ".correctness-2.0",
        Track.Validation_Violation_2_0: ".violation-2.0",
    }.get(track_details.track, "")
    is_svcomp_validation = (
        track_details.competition == Competition.SV_COMP
        and track_details.track != Track.Verification
    )

    if track_details.competition == Competition.TEST_COMP:
        config.point_interval *= 5
    if is_svcomp_validation:
        config.point_interval *= 5
    for category in category_info["categories_table_order"]:
        commands = []
        quantile_plot_show = f"""
set terminal {config.plot_format}
set output 'quantilePlot-{category}{validator}.{file_format}'
set tmargin {config.t_margin}
set bmargin 0
set lmargin {config.l_margin}
set rmargin {config.r_margin}
unset xlabel
unset xtics
{header.y_label}
# for Test-Comp 2022 pdf
#set key at 1710, 4200
set key top left
{header.scale}
set pointsize 1.0
set multiplot layout 2,1
set size {config.size_a[0]},{config.size_a[1]}
set origin {config.origin_a[0]},{config.origin_a[1]}
"""
        x_max = 0
        x_min = 0
        y_max = 0
        y_min = 0
        tool_list = utils.get_competition_tools(fm_tools_catalog, track_details)
        for tool in tool_list:
            tool_name = fm_tools_catalog[tool].name
            if is_svcomp_validation:
                tool_name += f" (w{validator.split("-")[-1]})"
            tool_file = os.path.join(
                plot_dir,
                f"QPLOT.{category}.{tool}.quantile-plot{validator}.csv",
            )
            tool_short = get_tool_name(tool_name)
            gnuplot_dashtype = 1
            gnuplot_pointsize = 1
            if "meta_tool" in utils.get_participation_labels(
                fm_tools_catalog,
                tool,
                category_info["year"],
                track_details.competition,
                track_details.track,
            ):
                gnuplot_dashtype = 2
                gnuplot_pointsize = 0.7
            # "inactive" takes precedence over "meta_tool" (inactive meta_tool is drawn as "inactive")).
            if "inactive" in utils.get_participation_labels(
                fm_tools_catalog,
                tool,
                category_info["year"],
                track_details.competition,
                track_details.track,
            ):
                gnuplot_dashtype = 3
                gnuplot_pointsize = 0.7

            if not os.path.isfile(tool_file):
                logging.debug("Missing %s", tool_file)
                continue
            else:
                csv_df = pd.read_csv(tool_file, sep="\t", index_col=False, header=None)
                csv_df.columns = ["c1", "c2"]
                csv_df.sort_values(by=["c1", "c2"])
                csv_df.to_csv(tool_file, sep="\t", header=None, index=None)
            with open(tool_file, "r") as fp:
                lines = fp.readlines()
                if lines:
                    x, y = line_to_tuple(lines[0])
                    x_min = min(x_min, x)
                    y_min = min(y_min, y)
                    x, y = line_to_tuple(lines[-1])
                    x_max = max(x_max, x)
                    y_max = max(y_max, y)

            try:
                line_color = list(
                    color_map[color_map["tool"] == fm_tools_catalog[tool].name]["color"]
                )[0]
                point_type = list(
                    color_map[color_map["tool"] == fm_tools_catalog[tool].name]["mark"]
                )[0]
            except Exception:
                logging.error(
                    f"Could not find tool {fm_tools_catalog[tool].name} in color map."
                )

            commands.append(
                f"'{tool_file}' using 1:2 with linespoints linecolor rgb \"{line_color}\" dashtype {gnuplot_dashtype} pointtype {point_type} pointinterval {config.point_interval} pointsize {gnuplot_pointsize} linewidth {config.line_width} title '{tool_short}'"
            )

        if not commands:
            logging.debug(f"Missing data for {category}")
            continue

        if x_min < -x_max / 2:
            x_min = -x_max / 2
        if x_min > -x_max / 4:
            x_min = -x_max / 4

        x_max_rounding_box = 100
        x_min_rounding_box = 100
        x_range = x_max - x_min

        if x_range < 500:
            x_max_rounding_box = 10
            x_min_rounding_box = 50

        x_max = (x_max / x_max_rounding_box + 1) * x_max_rounding_box
        x_min = (x_min / x_min_rounding_box - 1) * x_min_rounding_box

        y_max_rounding_box = 100
        y_range = y_max - y_min

        if y_range < 500:
            y_max_rounding_box = 10

        y_max = (y_max / y_max_rounding_box + 1) * y_max_rounding_box

        if category_info["competition"] == "SV-COMP":
            footer = f"set xrange [{int(x_min)}:{int(x_max)}]\nset yrange[1:1000]\n"
        else:
            footer = (
                f"set xrange [0:{int(x_max)}]\n"
                f"set yrange[0:{int(y_max)}]\n"
                f"{header.x_label}\n"
                f"set xtics nomirror"
            )

        quantile_plot_show += f"\n{footer}\nplot {','.join(commands)};"
        if category_info["competition"] == "SV-COMP":
            quantile_plot_show += f"""
unset logscale
set yrange [0:1]
unset key
unset bmargin
set tmargin 0
set xtics nomirror
unset ytics
unset ylabel
set size {config.size_b[0]},{config.size_b[1]}
set origin {config.origin_b[0]},{config.origin_b[1]}
{header.x_label}
plot {",".join(commands)};
    """
        with open(f"quantilePlotShow{validator}.gp", "w") as fp:
            fp.write(quantile_plot_show)

        p = subprocess.Popen(["gnuplot", f"quantilePlotShow{validator}.gp"])
        logging.debug(p.communicate())

        exit_code = os.system(
            f"/bin/mv quantilePlot-{category}{validator}.{file_format} {results_dir};"
        )
        if exit_code != 0:
            logging.error(
                f"Error moving result files. Exit code from 'mv': {exit_code}."
            )
            sys.exit(1)
    exit_code = os.system(f"/bin/mv quantilePlotShow{validator}.gp {results_dir};")
    if exit_code != 0:
        logging.error(
            f"Error moving example GNUplot program. Exit code from 'mv': {exit_code}."
        )
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Process command line arguments.")
    base_path = Path(__file__).parent.parent.parent
    parser.add_argument(
        "-o",
        "--output",
        help="Folder to store the generated quantile-plot files.",
        default=base_path / "results-verified",
    )
    parser.add_argument(
        "-f",
        "--format",
        help="Export format: svg, png, pdf",
        choices={"svg", "pdf", "png"},
        default="pdf",
    )
    parser.add_argument(
        "-t",
        "--fm-tools",
        help="Path to fm-tools",
        default=base_path / "fm-tools" / "data",
    )
    parser.add_argument(
        "-c",
        "--category-info",
        help="Path to the category-info.yml",
        default=base_path / "benchmark-defs" / "category-structure.yml",
    )
    parser.add_argument(
        "-i",
        "--input",
        help="Folder to read the input data in CSV format.",
        # We want a relative path here, because this path is written to an output file.
        default=os.path.relpath(base_path / "results-qplots"),
    )
    parser.add_argument(
        "-m",
        "--mark",
        help="TSV file indicating how to colorize tools and which marker to use.",
        required=False,
    )
    parser.add_argument(
        "-v",
        "--validation-type",
        choices={"violation1.0", "correctness1.0", "violation2.0", "correctness2.0"},
        help="Set this parameter to one of the two valid values (correctness, violation) to indicate that the script should generate the plots for validators."
        "Files for validator runs have different file endings and a combination of the runs for all verifiers is needed.",
        required=False,
    )
    return parser.parse_args()


def main():
    parsed = parse_arguments()
    results_dir = parsed.output
    plot_dir = parsed.input
    with open(parsed.category_info) as inp:
        try:
            category_info = yaml.load(inp, Loader=yaml.FullLoader)
        except yaml.YAMLError as e:
            logging.error(e)
            sys.exit(1)
    file_format = parsed.format

    competition = competition_from_string(category_info["competition"])
    year = category_info["year"]
    header = Header.get_header(competition)
    config = Configuration.get_configuration(file_format)

    # Colors in GNUplot: https://i.stack.imgur.com/x6yLm.png
    # Dash types: https://gnuplot.sourceforge.net/demo/dashtypes.html
    color_file = (
        parsed.mark
        if parsed.mark
        else Path(__file__).parent / "qPlotMapColorPointType.tsv"
    )

    color_map = pd.read_csv(color_file, sep="\t", index_col=False, header=None)
    color_map.columns = ["tool", "color", "mark"]

    track = (
        Track.Verification
        if parsed.validation_type is None
        else {
            "violation1.0": Track.Validation_Violation_1_0,
            "correctness1.0": Track.Validation_Correct_1_0,
            "violation2.0": Track.Validation_Violation_2_0,
            "correctness2.0": Track.Validation_Correct_2_0,
        }[parsed.validation_type]
    )
    if competition == Competition.TEST_COMP:
        track = Track.Test_Generation
    track_details = TrackDetails(competition, track, year)
    generate_plots(
        category_info,
        color_map,
        file_format,
        header,
        config,
        plot_dir,
        results_dir,
        fm_tools_path=parsed.fm_tools,
        track_details=track_details,
    )


if __name__ == "__main__":
    main()
