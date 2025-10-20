# SV-COMP Reproducibility - Overview

This repository describes the configuration of the competition machines (below)
and the benchmark definition for each verifier (folder [benchmark-defs/](benchmark-defs/)),
in order to make results of the competition reproducible.



# Components for Reproducing Competition Results

The competition uses several components to execute the benchmarks.
The components are described in the following table.

| Component              | Repository                                                      | Participants             |
| ---                    | ---                                                             | ---                      |
| Verification Tasks     | https://gitlab.com/sosy-lab/benchmarking/sv-benchmarks          | add, fix, review tasks   |
| Benchmark Definitions  | https://gitlab.com/sosy-lab/sv-comp/bench-defs                  | define their parameters  |
| Tool-Info Modules      | https://github.com/sosy-lab/benchexec/tree/main/benchexec/tools | define inferface         |
| Verifiers              | https://gitlab.com/sosy-lab/benchmarking/fm-tools               | submit to participate    |
| Benchmarking Framework | https://github.com/sosy-lab/benchexec                           | (use to test their tool) |
| Competition Scripts    | https://gitlab.com/sosy-lab/benchmarking/competition-scripts    | (use to reproduce)       |
| Witness Format         | https://github.com/sosy-lab/sv-witnesses                        | (know)                   |
| Task-Definition Format | https://gitlab.com/sosy-lab/benchmarking/task-definition-format | (know)                   |
| Remote Execution       | https://gitlab.com/sosy-lab/software/coveriteam                 | (use to test their tool) |

Archives published at Zenodo:

| Year | Verification Tasks                      | Tools                                   | Competition Results                     | Verification Witnesses                  | BenchExec                               |
| ---  | ---                                     | ---                                     | ---                                     | ---                                     | ---                                     |
| 2024 | https://doi.org/10.5281/zenodo.10669723 | https://doi.org/10.5281/zenodo.10669735 | https://doi.org/10.5281/zenodo.10669731  | https://doi.org/10.5281/zenodo.10669737 | https://doi.org/10.5281/zenodo.10671136 |
| 2023 | https://doi.org/10.5281/zenodo.7627783  | https://doi.org/10.5281/zenodo.7627829  | https://doi.org/10.5281/zenodo.7627787  | https://doi.org/10.5281/zenodo.7627791  | https://doi.org/10.5281/zenodo.7612021  |
| 2022 | https://doi.org/10.5281/zenodo.5831003  |                                         | https://doi.org/10.5281/zenodo.5831008  | https://doi.org/10.5281/zenodo.5838498  | https://doi.org/10.5281/zenodo.5720267  |
| 2021 | https://doi.org/10.5281/zenodo.4459126  |                                         | https://doi.org/10.5281/zenodo.4458215  | https://doi.org/10.5281/zenodo.4459196  | https://doi.org/10.5281/zenodo.4317433  |
| 2020 | https://doi.org/10.5281/zenodo.3633334  |                                         | https://doi.org/10.5281/zenodo.3630205  | https://doi.org/10.5281/zenodo.3630188  | https://doi.org/10.5281/zenodo.3574420  |
| 2019 | https://doi.org/10.5281/zenodo.2598729  |                                         |                                         | https://doi.org/10.5281/zenodo.2559175  | https://doi.org/10.5281/zenodo.1638192  |
| 2018 |                                         |                                         |                                         |                                         |                                         |
| 2017 |                                         |                                         |                                         |                                         |                                         |
| 2016 | https://doi.org/10.5281/zenodo.1158644  |                                         |                                         |                                         |                                         |


# Instructions for Execution and Reproduction

Concrete instructions on how to execute the experiments and to reproduce the results of the competition are available here:
https://gitlab.com/sosy-lab/benchmarking/competition-scripts/#instructions-for-execution-and-reproduction



# Computing Environment on Competition Machines

## Installed Ubuntu packages

A description of all installed Ubuntu packages, with their versions is given here:
https://gitlab.com/sosy-lab/benchmarking/competition-scripts/#installed-ubuntu-packages

## Docker Image

SV-COMP provides a Docker image that tries to provide an environment
that has mostly the same packages installed as the competition machines.
The Docker image is described here:
https://gitlab.com/sosy-lab/benchmarking/competition-scripts/#container-image

## Parameters of RunExec

The parameters that are passed to the [BenchExec](https://github.com/sosy-lab/benchexec) [1]
executor [runexec](https://github.com/sosy-lab/benchexec/blob/main/doc/runexec.md) on the competition machines
are described here:
https://gitlab.com/sosy-lab/benchmarking/competition-scripts/#parameters-of-runexec



# References

[1]: Dirk Beyer, Stefan Löwe, and Philipp Wendler.
     Reliable Benchmarking: Requirements and Solutions.
     International Journal on Software Tools for Technology Transfer (STTT), 21(1):1-29, 2019.
     https://doi.org/10.1007/s10009-017-0469-y


