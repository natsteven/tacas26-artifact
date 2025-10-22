SPDX-License-Identifier: CC-BY-4.0

This directory contains presentations about tools described in the `data/` directory.

A presentation entry consists of two files:
- `presentations/<tool-id>_<event-id>.pdf` and
- `presentations/<tool-id>_<event-id>.pdf.license`
where `<tool-id>` matches one of the file names `data/<tool-id>.yml`
and `<event-id>` identifies the event where the presentation is given.

The file with extension `pdf` contains a presentation in PDF/A format.
The file with extension `license` contains an SPDX identifier of the license.
Please use the following contents for this file:
```
SPDX-License-Identifier: CC-BY-4.0
```
Instead of CC-BY-4.0 you can use a different license,
but CC-BY-4.0 is strongly recommended for presentation files.

Examples:
https://gitlab.com/sosy-lab/benchmarking/fm-tools/-/tree/main/presentations

