import benchexec.benchexec

import sys
import csv
import hashlib


def hash(text):
    return hashlib.sha256(text).digest()


class FingerPrinter(benchexec.BenchExec):
    def execute_benchmark(self, benchmark_file):
        benchmark = benchexec.Benchmark(
            benchmark_file,
            self.config,
            self.config.start_time or benchexec.util.read_local_time(),
        )
        print(
            "I'm fingerprinting %r consisting of %s run sets using %s %s."
            % (
                benchmark_file,
                len(benchmark.run_sets),
                benchmark.tool_name,
                benchmark.tool_version or "(unknown version)",
            )
        )
        with open(
            ".".join([benchmark.name, "fingerprints.csv"]), "w", newline=""
        ) as csvfile:
            writer = csv.writer(csvfile, delimiter="\t")
            writer.writerow(
                [
                    "identifier",
                    "propertyfile",
                    "expected_result",
                    "sources",
                    "fingerprint",
                ]
            )
            for run_set in benchmark.run_sets:
                for run in run_set.runs:
                    expected_result = run.expected_results[run.propertyfile]
                    fingerprint = hashlib.sha256()
                    fingerprint.update(hash(open(run.propertyfile, "rb").read()))
                    fingerprint.update(hash(str(expected_result).encode("utf-8")))
                    for progname in run.sourcefiles:
                        fingerprint.update(hash(progname.encode("utf-8")))
                        fingerprint.update(hash(open(progname, "rb").read()))
                    writer.writerow(
                        [
                            run.identifier,
                            run.propertyfile,
                            expected_result,
                            run.sourcefiles,
                            fingerprint.hexdigest(),
                        ]
                    )
        return 0


benchexec = FingerPrinter()
benchexec.main(benchexec=FingerPrinter(), argv=sys.argv)
