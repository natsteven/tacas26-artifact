# TACAS 2026 Artifact

- Submission: 2200
- Title: A-Str: Acyclic String Constraint Solver with Native Java String API Support
- DOI: [10.5281/zenodo.17428647](https://doi.org/10.5281/zenodo.17428647)

## Requirements

This artifact has been designed for the [TACAS '26 Virtual Machine](https://zenodo.org/records/17171929) but should be portable to most Linux distributions. 
It relies on apt and dpkg and expects Python 3 to be installed.
It also assumes that systemd with cgroups v2 is available (true for recent distros).
The system should have 8 GB RAM and at least 2 CPU cores.
It is set up to run experiments that evaluate string solvers on various benchmarks.


The following instructions assume you are at the artifact directory root, i.e. you have downloaded the artifact and/or unzipped its archive on the Virtual Machine, are using the terminal, and have navigated to, for example: `~/tacas26-artifact`

## Structure

- `A-Str` contains the source code for the A-Str tool.

- `benchmarks` contains the benchmarks run for the SMT-solver experiments.
As explained in the tool paper, this includes a compatible selection of the `QF_S` set from [SMT-LIB 2025](zenodo.org/records/15493090), and those from real-world Java programs.
More explanation is below.

- `bin` contains the binaries/jars and wrapper scripts for running a given smt-solver.

- `data` contains results from the experiment presented in the accompanying tool paper.
We include a supplementary graph of the solvers' times on the SMT-LIB benchmarks omitting the rna benchsets.
The reasoning behind this is discussed in the following section.

- `results` is where experimental results end up.

- `scripts` contains various scripts for running smt-solvers and collecting/processing data.

- `sv-comp` is where the SV-COMP and SPF experiments scripts and framework are located.
This is a subset of the repository located at https://gitlab.com/sosy-lab/sv-comp/bench-defs

- `util` contains some utilities.

Otherwise there is this README, a LICENSE, and four scripts that are explained in the following section.

## Reproducing Experiments

### Setup

To set up the VM with the proper packages, run the init.sh script using:
```bash
./init.sh
```
This will install some dependencies and perform some cgroup workaround management for benchexec.

### Smoketest

Run the smoketest using:
```bash
./smoketest.sh
```
This runs each smt-solver on a selected SMT-LIB benchmark and places it in the results directory.
It then runs the SV-COMP framework on one of the sv-benchmarks and places its results in the results directory.

A basic validation of the results is included as part of this script.
You can check the smoketest results themselves in the `results/` directory.
As mentioned in the output, the files are `smoketest-spf-results.csv` and `smoketest-smt-results.csv`.

### Full Run

As mentioned, this was tested on the TACAS VM. It expects to have ~8 GB of RAM. To simulate the SMT-solver experiment performed in the paper, retrieve the results, and create graphs, you can run:
```bash
./run-smt.sh
```
This should take around 5 hours.
We limit the timeout to 60 seconds in contrast to the 120 used for the paper to improve runtime.
This only affects a small portion of the benchmarks.
We also choose not to run the rna-sat and rna-unsat benchmark sets in this script as all of these benchmarks timeout for two of the solvers.
This would waste something like 33 hours of compute time.
The user may adjust the script or otherwise see the descriptions below for running the solvers on specific benchmark sets.

After completion, the timing results for SMT-LIB benchmarks can be found at `results/smt-results.csv` and those for the real Java benchmarks at `results/real-results.csv`.
Additionally, graphs are produced and available as .pngs in the results directory.

Also note that the experiments for the paper were run on a high-performance cluster using SLURM for job allocation and resource management. 
Various changes were made to the scripts to enforce resource limits on the virtual machine.
If a process reaches these limits, we record it as a timeout.

To perform the SPF comparison between A-Str and z3str3 on the sv-benchmarks and supplemental benches you can run:
```bash
./run-spf.sh
```
This takes around 7 minutes.
The results for this run can be seen in the html and csv files: `results/results.<DATETIME>.table`
You are encouraged to open the html version with firefox for a user-friendly experience.

## Notes & Additional Usage

### A-Str 

Source code can be seen in `A-Str` as well as build instructions and usage.
The `run.sh` script provided in this directory allows the user to run the tool.
Usage with an .smt2 file uses our smt-lib parser to output a temporary json file.
This does not have any safeguards for timeouts or memory usage like the `run-smt.sh` or `scripts/smt-run.sh` scripts so use at your own risk.

### SMT-Solver Runs

The script provided in the `scripts/` directory allows a user to run any combination of solvers and benchmark sets for the SMT-solver evaluations.
Specifically, the `smt-run.sh` script takes as arguments a list of solvers and benchmark sets and runs those combinations. 
e.g. 
```bash
./scripts/smt-run.sh --s a-str,cvc5 --b rna-sat,woorpje
```
The `--s` and `--b` take a comma-separated (no whitespace) list of solvers and benchmark sets respectively.
They also accept simply 'all'.
The options for these are respectively [a-str, cvc5, ostrich, z3-noodler] and [automatark, matching, real, rna-sat, rna-unsat, woorpje].
Additionally, it accepts an override of the default 120 second timeout with `--timeout <time-in-secs>`.

All the benchmarks are in benchmarks where the `a-str` directory has all those for that solver, the `smt` directory contains all the SMT-LIB benches that are used with the other 3 solvers, and the `not-smt` directory contains the translated real-world Java benchmarks for each specific solver (other than A-Str).

Finally, individual runs on a specific solver and benchmark can be performed using `./scripts/run_solver.sh`.
This accepts the solver name as seen above and a full relative path to the specific benchmark.

Logs and timing can be found in the `smt-logs` directory.
The script `make-table.sh` compiles timing results for every solver and the benchmarks that have been run.
Note this assumes that the solvers have all been run on the same benchmark sets.
It takes arguments for the name of the output file and the set to be compiled: specifically 'smt', 'real', or 'all'.
For example, we would run:
```bash
./scripts/make-table.sh smt-results.csv smt
```
The `makegraph.py` script takes as input the path of a CSV (e.g. one produced by `make-table.sh`), as well as a name for titling.
Graphs are output into the results directory.

### SLURM

The scripts used for the distributed high-performance computing cluster can be found at `scripts/slurm`. 
Note that these are partially specific to the cluster the experiments were performed on and require the run_solver script as well as the solvers and wrapper scripts in `bin`.

### SV-COMP Runs of SPF

The main driver for the SV-COMP benchmarking is `sv-comp/myRunVerify.sh`.
This points to the definition file `sv-comp/spf.xml` which in turn points at the benchmark set file `sv-comp/Strings.set`.
Users could set up different subsets of the benchmarks or otherwise adjust the definition file if they so choose. 
We point to the https://gitlab.com/sosy-lab/sv-comp/bench-defs repository for extensive documentation on this framework.

### Converting SMT-LIB to JSON

If you would like to only convert a `.smt2` to our `.json` DFG format, use `util/getSMT.sh` with a directory or file path and optional output path. Note that this uses `A-Str/tools/smtlib-converter.jar` and the `A-Str/run.sh` will accept a `.smt2` file and create temporary `.json` using it.

## Badges

This artifact is intended to satisfy the Available, Functional, and Reusable Artifact Evaluation badge requirements.