# tacas26-artifact
Artifact for a TACAS '26 tool paper containing results/data as well a reproducability package for the A-Str tool

## Docker notes:

Dockerfile details
Installs:
openjdk-17-jre-headless (Java)
time and bc (used by run_solver.sh)
dos2unix (normalize scripts)
tini (proper signal handling)
Copies the entire repo to /app and ensures scripts and binaries are executable.
Defaults:
ENTRYPOINT via tini for clean shutdown.
CMD to a bash shell.
TIMEOUT_SECS default 120s.

Build the image:
`docker build -t tacas26:local .`

Run a bash shell in the container (mount your repo if you want live edits):

`docker run --rm -it -v "$PWD:/app" -w /app tacas26:local`

Run a local batch identical to SLURM logic:
inside container (or as docker run ... scripts/run_local.sh ...):
`scripts/run_local.sh --s all --b automatark,matching --timeout 120`

Logs:
Written to ./logs/<solver>/<benchset>/ (in your mounted repo if you used -v "$PWD:/app").
Adjust timeout via env:
`TIMEOUT_SECS=180 scripts/run_local.sh --s cvc5,ostrich --b real,simple`

Optional one-liners:
docker run --rm -it -v "$PWD:/app" -w /app -e TIMEOUT_SECS=120 tacas26:local \
  scripts/run_local.sh --s all --b automatark,matching

Without interactive shell:
docker run --rm -it -v "$PWD:/app" -w /app -e TIMEOUT_SECS=120 tacas26:local \
  scripts/run_local.sh --s all --b automatark,matching

Notes and edge cases
Binaries: The image chmod +x /app/bin/* assumes your static binaries are in bin and are Linux-compatible. If any require glibc versions not matching Debian slim, we may need to switch base or include compatibility libs.
File lists: The local runner will skip missing benchmark files with a warning (does not abort the whole run).
Memory/timeouts: run_solver.sh still records mem/timeouts by exit code and captures time stats in .time files.
Python analysis: You can use your existing Python scripts (run.py, summary.py) inside the container since Python is included.
Quick verification

Add a small smoketest target that runs a tiny subset to validate environment quickly.

If you want, I can also add a docker-compose.yml that sets up volume mounts and default TIMEOUT_SECS, making runs simpler.

