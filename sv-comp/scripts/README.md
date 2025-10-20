# Competition Scripts - Overview

This repository contains scripts and definitions that are useful to execute
benchmark experiments for competitions of automatic tools,
like solvers, verifiers, and test generators.

The scripts are based on the benchmarking framework [BenchExec](https://github.com/sosy-lab/benchexec) [1].



# Instructions for Execution and Reproduction

Competition-specific definitions of all relevant repositories, components, and benchmark definitions
are provided in the competition-specific repositories.

- SV-COMP uses this repository as as submodule in repository https://gitlab.com/sosy-lab/sv-comp/bench-defs

  Documentation of all components: https://gitlab.com/sosy-lab/sv-comp/bench-defs/-/tree/main#components-for-reproducing-competition-results

- Test-Comp uses this repository as as submodule in repository https://gitlab.com/sosy-lab/test-comp/bench-defs

  Documentation of all components: https://gitlab.com/sosy-lab/test-comp/bench-defs/-/tree/main#components-for-reproducing-competition-results

In the following, we explain concrete instructions for how to use the scripts in this repository
to execute experiments and reproduce results of the competitions.

## Setup

The following steps set up the benchmarking environment:
- `mkdir mycomp` (where `mycomp` is a new directory in which we store everything)
- `cd mycomp` (this directory is assumed to be the current working directory from now on)
- One of the following:
  - SV-COMP:   `git clone https://gitlab.com/sosy-lab/sv-comp/bench-defs.git ./`
  - Test-Comp: `git clone https://gitlab.com/sosy-lab/test-comp/bench-defs.git ./`
- `git checkout svcomp23` (if you want to reproduce SV-COMP 2023)
- `make init` (takes a while: downloads several GB of data from repositories)
- [`make update`] (only if you want to work with the latest version) 

For reproducing results of a specific edition of the competition, please checkout the tag for that edition.

The following sections assume that the working directory is the same in which the above commands were executed.

## Required Packages

- Install required Python packages: `pip install --requirement scripts/requirements.txt`
- `xmlstarlet` is not (yet) available since python3.11 as a binary release, and source-based installation fails easily. Either install it via the distro's package manager (e.g., `apt install xmlstarlet`), or as an alternative, one can use [this statically linked binary](https://github.com/acjohnson/xmlstarlet-static-binary/raw/9dd0bf44aecfa899dedecd57340e6c6985f63592/xmlstarlet) in a folder on $PATH, and remove the entry from `requirements.txt`

## Executing a Benchmark for a Particular Tool

Assume that we would like to reproduce results for the tool `CPAchecker`,
including results validation.
This can be achieved using the following command:

`scripts/execute_runs/mkRunVerify.sh cpachecker`

The above command executes the verification runs with tool `CPAchecker`, and
afterwards all result validators that are declared in `benchmark-defs/category-structure.yml`.

A detailed explanation how the above step downloads and unpacks a tool,
go to Section [Detailed Execution of Tools](#detailed-execution-of-tools).

## Executing Only Runs for Producing Results

Results are produced by verification tools and by test-generation tools.
Verification tools produce as result a verification verdict and a verification witnesses,
and test-generation tools produce a test suite.

If we would like to execute only verification runs, then we can use the following command:

```
scripts/execute_runs/execute-runcollection.sh \
    benchexec/bin/benchexec \
    archives/2023/cpachecker.zip \
    benchmark-defs/cpachecker.xml \
    witness.graphml \
    .graphml \
    results-verified/
```

Similarly, if we would like to execute only test-generation runs, then we can use the following command:

```
scripts/execute_runs/execute-runcollection.sh \
    benchexec/bin/benchexec \
    archives/2023/coveritest.zip \
    benchmark-defs/coveritest.xml \
    test-suite.zip \
    .zip \
    results-verified/
```

The parameters specify the:
- benchmarking utility (BenchExec) to be used to run the benchmark,
- tool archive,
- benchmark definition,
- name of the witness files, to which the unification script links the witness produced by the tool,
- pattern using which the unification script searches for produced witnesses,
- the directory in which the results shall be stored, and
- (optional) parameters to be passed to the benchmarking utility.

For quick tests and sanity checks, BenchExec can be told to restrict the execution to a certain test-set.
For example, to restrict the execution to the sub-category `ReachSafety-ControlFlow`,
you add an extra parameter `-t ReachSafety-ControlFlow` that is passed to the benchmarking utility.

Furthermore, BenchExec can be told to overwrite limit from the benchmark definitions (which should be used only for test executions).
To see if a tool generally works and produces outputs, you could use (assuming we use a machine with 8 cores and 30 GB of RAM)
the additional parameters `--timelimit 60 --memorylimit 3GB --limitCores 1 --numOfThreads 8` to
- limit the CPU time to `60 s`,
- limit the memory to `3 GB`,
- limit the number of cores to `1`, and
- set the number of runs executed in parallel to `8`.

It is important to execute the tools (when running experiments) in a container.
Since we use BenchExec, this is done automatically.
In order to protect our file system and to give proper write access to the tool inside the container,
we add the setup of the overlay filesystem using the parameters
- `--read-only-dir /` to make sure the tool we execute does not write at unexpected places,
- `--overlay-dir /home/` to let BenchExec setup a directory for the tool inside the container, and
- `--overlay-dir ./` to give permission to write to the working directory.

A complete command line would look as follows:

```
scripts/execute_runs/execute-runcollection.sh \
    benchexec/bin/benchexec \
    archives/2023/cpachecker.zip \
    benchmark-defs/cpachecker.xml \
    witness.graphml \
    .graphml \
    results-verified/ \
    -t ReachSafety-ControlFlow \
    --timelimit 60 --memorylimit 3GB --limitCores 1 --numOfThreads 8 \
    --read-only-dir / --overlay-dir /home/ --overlay-dir ./
```

**Note:** If you execute [CoVeriTeam](https://gitlab.com/sosy-lab/software/coveriteam/)-based tools, or other tools that use CGroups, then the following additional parameter is necessary:
`--full-access-dir /sys/fs/cgroup`.

## Executing Only Validation Runs (Incl. Witness Linter)

The above executions produce results (witnesses) in a results directory similar to `cpachecker.2021-12-03_10-39-40.files/`
inside the output directory `results-verified/`.

The benchmark definition for validation must be updated with this results directory:
The string `results-verified/LOGDIR/` must be replaced by the string `results-verified/cpachecker.2021-12-03_10-39-40.files/`

Suppose we would like to run result validation for violation results with CPAchecker.
We would make a copy of `cpachecker-validate-violation-witnesses.xml` to `cpachecker-validate-violation-witnesses-cpachecker.xml`
and replace the string as mentioned above there. The we can run:

```
scripts/execute_runs/execute-runcollection.sh \
    benchexec/bin/benchexec \
    archives/2023/val_cpachecker.zip \
    benchmark-defs/cpachecker-validate-violation-witnesses-cpachecker.xml \
    witness.graphml \
    .graphml \
    ../../results-validated/ \
    -t ReachSafety-ControlFlow \
    --memorylimit 3GB --limitCores 1 --numOfThreads 8 \
    --read-only-dir / --overlay-dir /home/ --overlay-dir ./
```

Suppose we would like to run the witness linter to check that the witnesses are syntactically valid.
We would make a copy of `witnesslint-validate-witnesses.xml` to `witnesslint-validate-witnesses-cpachecker.xml`
and replace the string as mentioned above there. Then we can run:

```
scripts/execute_runs/execute-runcollection.sh \
    benchexec/bin/benchexec \
    archives/2023/val_witnesslint.zip \
    benchmark-defs/witnesslint-validate-witnesses-cpachecker.xml \
    witness.graphml \
    .graphml \
    results-validated/ \
    -t ReachSafety-ControlFlow \
    --read-only-dir / --overlay-dir /home/ --overlay-dir ./
```


## Detailed Execution of Tools

In the following we explain some of the steps that the script `scripts/execute_runs/execute-runcollection.sh` normally performs for us.

### Download a Tool from Zenodo

The following command downloads the tool `CPAchecker`:
- `fm-tools/lib-fm-tools/python/src/fm_tools/update_archives.py cpachecker`

### Unpack a Tool

The following command unpacks the tool `CPAchecker`:
- `mkdir bin/cpachecker-32KkXQ0CzM`
- `scripts/execute_runs/mkInstall.sh archives/2023/cpachecker.zip bin/cpachecker-32KkXQ0CzM`

### Assemble Provenance Information for a Tool

The following command prints information about the repositories and their versions:
- `scripts/execute_runs/mkProvenanceInfo.sh archives/2023/cpachecker.zip`

### Execute a Benchmark for a Tool

- `cd bin/cpachecker-32KkXQ0CzM`
- `../../benchexec/bin/benchexec ../../benchmark-defs/cpachecker.xml --outputpath ../../results-verified/ -t ReachSafety-ControlFlow`

### Initialize Result Files (for Validation Runs and Reproduction)

The script `scripts/execute_runs/execute-runcollection.sh` also performs some post-processing steps to:
- create a mapping from files to SHA hashes (for output files like witnesses, and for input files like programs, specifications, and task definitions) and
- create a symbolic link at a uniform location of the result files (in order to be able to feed the results as input to validation runs).



# Computing Environment on Competition Machines

The following instructions are specific to competitions that are executed on the compute cluster at LMU Munich (Apollon machines),
and try to explain the computing environment that is used for the competitions.


## Installed Ubuntu packages

A list of Ubuntu packages that are installed on the competition packages is available here:
https://gitlab.com/sosy-lab/benchmarking/competition-scripts/-/blob/main/test/Dockerfile.user.2025
The specific versions of the packages are provided here:
https://gitlab.com/sosy-lab/benchmarking/competition-scripts/-/blob/main/test/Ubuntu-packages.txt


## Container Image
The competition provides a container image that tries to provide an environment
that has mostly the same packages installed as the competition machines:
- Image definition: https://gitlab.com/sosy-lab/benchmarking/competition-scripts/-/blob/main/test/Dockerfile.user.2025
- Image name: `registry.gitlab.com/sosy-lab/benchmarking/competition-scripts/user:latest`
- Test if the tool works with the installation:
  - Unzip tool archive to temporary directory `<TOOL>` (**`<TOOL>` must be an absolute path!**)
  - `podman pull registry.gitlab.com/sosy-lab/benchmarking/competition-scripts/user:latest`
  - `podman run --rm -i -t --volume=<TOOL>:/tool --workdir=/tool registry.gitlab.com/sosy-lab/benchmarking/competition-scripts/user:latest bash`
  - Start tool
  - Of course, other container runtimes than Podman (like Docker) can also be used.


## Parameters of RunExec

<!-- Fetch latest version from the Ansible configuration for the competition machines:
https://gitlab.ifi.lmu.de/sosy-lab/admin/sysadmin/ansible/-/blob/master/roles/vcloud-worker/templates/Config.j2
Last synchronized: 2020-12-05 from commit 670c4eb
-->

```
--container
--read-only-dir /
--hidden-dir /home
--hidden-dir /var/lib/cloudy # environment-specific
--set-cgroup-value pids.max=5000
--output-directory <work-dir>
--overlay-dir <run-dir>
--quiet
--maxOutputSize 2MB
--dir <work-dir>
--output <logfile>
--full-access-dir /sys/fs/cgroup # competition-specific
--timelimit <depends on benchmark XML>
--softtimelimit 900s # only if specified in benchmark XML
--memlimit 15GB
--memoryNodes 0 # hardware-specific
--cores 0,4,1,5 # hardware-specific
```



# References

[1]: Dirk Beyer, Stefan Löwe, and Philipp Wendler.
     Reliable Benchmarking: Requirements and Solutions.
     International Journal on Software Tools for Technology Transfer (STTT), 21(1):1-29, 2019.
     https://doi.org/10.1007/s10009-017-0469-y


