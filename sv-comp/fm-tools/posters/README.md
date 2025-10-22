SPDX-License-Identifier: CC-BY-4.0

This directory contains posters about tools described in the `data/` directory.

A poster entry consists of two entries:
- `posters/<tool-id>_<event-id>.pdf` and
- `posters/<tool-id>_<event-id>.pdf.license`
where `<tool-id>` matches one of the file names `data/<tool-id>.yml`
and `<event-id>` identifies the event where the poster was presented.

The file with extension `pdf` contains a presentation with the following specs:
- PDF/A format
- portrait orientation
- ISO *A{0-4}* page format
- file size max. 10 MB

The file with extension `license` contains an SPDX identifier of the license.
Please use the following contents for this file:
```
SPDX-License-Identifier: CC-BY-4.0
```
Instead of CC-BY-4.0 you can use a different license,
but CC-BY-4.0 is strongly recommended for presentation files.

Examples:
https://gitlab.com/sosy-lab/benchmarking/fm-tools/-/tree/main/presentations

