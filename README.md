# TACAS '26 Artifact
This artifact is hosted at https://zenodo.org/records/17428647.
It is for a TACAS '26 tool paper containing results/data as well a reproducability package for the A-Str tool.
This has been constructed to work on the TACAS '26 VM provided at https://zenodo.org/records/17171929.
The following instructions assume you are at the artifact directory root.

## General Info
The `benchmarks` directory contains the benchmarks run for the smt-solver experiments.
As explained in the tool paper this includes a selction of SMT-LIB benches and those from real-world Java programs.
More explanation is below.

`bin` contains the binaries/jars and wrapper scripts for running a given smt-solver.

`data` contains results from the experiment presented in the accompanying tool paper.
We include a supplementary graph of the solvers' times on the SMT-LIB benchmarks omitting the rna benchsets.
The reasoning behind this is discussed in the following section.

`results` is where experimental results end up.

`scripts` contains various scripts for running smt-solvers and collecting/processing data.

`sv-comp` is where the SV-COMP and SPF experiments scripts and framework are located.
This is a subset of the repository located at https://gitlab.com/sosy-lab/sv-comp/bench-defs

`util` contains some basic utilities.

Otherwise we have our main scripts for running experiments.

## Reproducing Experiments

### Setup
To setup the VM with the proper packages run the init.sh script using:
```bash
./init.sh
```
This install some dependencies and perofrms some cgroup workaround management for benchexec.

### Smoketest
Run the smoketest using:
```
./smoketest.sh
```
This runs each smt-solver on a selected SMT-LIB benchmark and places it in the results directory.
It then runs the SV-COMP framework on one of the sv-benchmarks and places its results in the results directory.

A basic validation of the results is included as part of this script.
You can check the smoketest results for themselves in the `results/` directory
As mentioned in the output the files are `smoketest-spf-results.csv` and `smoketest-smt-results.csv`

### Full Run
To simulate the smt-solver experiment performed in the paper, retrieve the results, as well as create graphs you can run:
```
./run-smt.sh
```
This should take around 2 hours.
It is important to note that we choose not to run the rna-sat and rna-unsat benchmark sets in this script as all 1000 of the benches timeout for two of the solvers.
This would waste something like 67 hours of compute time.
The user may adjust the script or otherwise see the descriptions below for running the solvers on specific benchmark sets, but we felt it unnecessary to include these sets in our simulated run.

After completion the timing results for SMT-LIB benchmark can be found at `results/smt-results.csv` and those for the real Java benchmarks at `results/real-results.csv`.
Additionally graphs are produced and available as .pngs in the results directory.

Also note that the experiments for the paper were run on a high-performance cluster using SLURM for jobs allocation and resource management. 
Various changes were made to the scripts to enforce resource limits on the virtual machine.
If a process reaches these limits we specify

To perform the SPF comparison between A-Str and z3str3 on the sv-benchmarks and supplemental benches you can run:
```
run-spf.sh
```
This takes around 7 minutes.
tThe results for this run can be seen in the html and csv files: `results/results.<DATETIME>.table`
You are encouraged to open the html version with firefox for a user-friendly experience.

## Additional Use
### SMT-Solver Runs
The script provided in the `scripts/` directory allow a user to run any combination of solvers and benchmark sets for the smt-solver evaluations.
Specifically the `smt-run.sh` script takes as arguments a list of solver and benchmark sets and runs those combinations. 
e.g. 
```
./scripts/smt-run.sh --s a-str,cvc5 --b rna-sat,woorpje
```
the `--s` and `--b` take a comma seperated (no whitespace) list of solvers and benchmark sets respectively.
They also accept simply 'all'.
The options for these are respectively [a-str, cvc5, ostrich, z3-noodler] and [automatark, matching, real, rna-sat, rna-unsat, woorpje].
Additionally it accepts an override of the default 120 second override with `--timeout <time-in-secs>`.

All the benchmarks are in benchmarks where the `a-str` directory has all those for that solver, the `smt` directory contains all the SMT-LIB benches that are used with the other 3 solvers, and the `not-smt` directory contains the translated real-world Java benchmarks for each specific solver (other than A-Str).

Finally, individual runs on a specific solver and benchmark can be performed using `./scripts/run_solver.sh`.
This accepts the solver name as seen above, and a full relative path to the specific benchmark.

Logs and timing can be found in the `smt-logs` directory.
The script `make-table.sh` compiles timing results for every solver and the benchmarks that have been run.
Note this assumes that the solvers have all been run on the same benchmark sets.
It takes arguments for the name of the output file and the set to be compiled: specifically 'smt','real' or 'all'.
For example we would run:
```
./scripts/make-table.sh smt-results.csv smt
```
The `makegraph.py` script takes as input the path of a csv (e.g. one produced my `make-table.sh`), as well as a name for titling.
Graphs are output into the results directory.

### SLURM
The scripts used for the distributed high-performance computing cluster can be found at `scripts/slurm`. 
Note that these are partially specific for the cluster experimetns were performed on and require the run_solver script as well as the file in `bin`

### SV-COMP Running
The main driver for the SV-COMP benching is `sv-comp/myRunVerify.sh`
This points to the definition file `sv-comp/spf.xml` which in turn points at the benchmark set file `sv-comp/Strings.set`.
User could set up different subsets of the benchmakrs or otherwise adjust the definition file if they so choose. 
We point to the https://gitlab.com/sosy-lab/sv-comp/bench-defs repository for extensive documentation on this framework.