# Tacas26-artifact
Artifact for a TACAS '26 tool paper containing results/data as well a reproducability package for the a-str tool.
This has been constructed to work on the TACAS '26 VM provided at https://zenodo.org/records/17171929.
Additionally it expect the artifact directory to be place in the home folder i.e. /home/tacas or $HOME as references are made to $HOME/tacas26-artifact
The following instructions assume you are at the artifact directory root.

## Tool Use

## Data from Paper's Experiments

## Reproducing Experiments

### Setup
To setup the VM with the proper packages run the init.sh script using:
`./init.sh`
This install some dependencies and perofrms some cgroup workaround management for benchexec.

### Smoketest
Run the smoketest using:
`./smoketest.sh`
This runs each smt-solver on a selected SMT-LIB benchmark and places it in the results directory.
It then runs the SV-COMP framework on one of the sv-benchmarks and places its results in the results directory.

A basic validation of the results is included as part of this script.
You can check the smoketest results for themselves in the `results/` directory
As mentioned in the output the files are `smoketest-spf-results.csv` and `smoketest-smt-results.csv`

### Full Run
To simulate the smt-solver experiment performed in the paper, retrieve the results, as well as create graphs you can run:
`./run-all-smt.sh`
Note that this will take around ~12 hours
After completion the timing results for SMT-LIB benchmark can be found at `results/smt-results.csv` and those for the real Java benchmarks at `results/real-results.csv`.
Additionally graphs are produced and available as .pngs in the results directory.

To perform the SPF comparison between A-Str and z3str3 on the sv-benchmarks and supplemental benches you can run:
`run-spf.sh`
The results for this run can be seen in the html and csv files: `results/results.<DATETIME>.table`
You are encouraged to open the html version with firefox for a user-friendly experience.
