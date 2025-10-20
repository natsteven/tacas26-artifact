#!/usr/bin/env python3

# This file is part of the competition environment.
#
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 Dirk Beyer <https://www.sosy-lab.org>


import csv
import sys


def trim(line: str) -> str:
    return line.strip()


def csv_to_html(csv_file, html_file):
    with open(csv_file, newline=None, encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile, delimiter="\t")
        header = next(reader)  # Read the header row

        with open(html_file, "w", encoding="utf-8") as htmlfile:
            htmlfile.write(
                """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" >
  <head>
    <meta http-equiv="content-language" content="en" />
    <meta http-equiv="Content-type" content="text/html;charset=UTF-8" />
    <meta http-equiv="Content-Language" content="en" />
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SV-COMP - Witness Classification</title>
    <style type="text/css">
      table {
        width: 100%;
        font-size: 80%;
        border-collapse: collapse;
        margin-top: 25px;
        position: relative;
        overflow: auto; /* Necessary for position: sticky to work in Chrome. */
      }
      thead tr th:first-child { /* Left-most header cell should overlap the other header cells when scrolling to the right. */
        z-index: 4;
      }
      thead tr th { /* Header row is sticky when scrolling down. */
        position: sticky;
        top: 0;
        z-index: 3;
        background-color: white;
        font-weight: bold;
      }
      th:first-child, td:first-child {  /* Left column is sticky when scrolling to the right. */
        position: sticky;
        left: 0;
        z-index: 2; /* Less than z-index of thead tr to put that on top during overlap. */
        background-color: white;
      }
      th, td {
        text-align: left;
        border-top: 2px solid gray;
        border-bottom: 2px solid gray;
      }
    </style>
  </head>

  <body>
"""
            )
            htmlfile.write(trim("    <table>\n"))
            htmlfile.write(trim("      <thead>\n"))
            htmlfile.write(trim("        <tr>\n"))
            htmlfile.write(
                trim("\n".join(trim(f"          <th>{value}</th>") for value in header))
            )
            htmlfile.write(trim("\n        </tr>\n"))
            htmlfile.write(trim("      </thead>\n"))
            htmlfile.write(trim("      <tbody>\n"))

            for row in reader:
                htmlfile.write(trim("      <tr>\n"))
                htmlfile.write(
                    trim("\n".join(trim(f"        <td>{value}</td>") for value in row))
                )
                htmlfile.write(trim("\n      </tr>\n"))

            htmlfile.write(trim("      </tbody>\n"))
            htmlfile.write(trim("    </table>\n"))
            htmlfile.write(
                """
    <p>Produced for SV-COMP.<p>
  </body>
</html>
"""
            )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py input.csv output.html")
    else:
        csv_to_html(sys.argv[1], sys.argv[2])
