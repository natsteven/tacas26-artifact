import os
import json
from . import mkRunWitnessStore

TEST_DIR = os.path.join(os.path.dirname(__file__), "test_mkRunWitnessStore")
assert os.path.exists(TEST_DIR)


def test_main():
    output_tests = os.path.join(TEST_DIR, "output_tests")
    fileByHash = os.path.join(TEST_DIR, "fileByHash")
    program_hash = "c117c02695ddb101583ad96117955e242a853299846ac846441a25e3775ce242"
    expected_file = os.path.join(
        TEST_DIR, "output_tests", "witnessListByProgramHashJSON", f"{program_hash}.json"
    )

    mkRunWitnessStore.main(["--output-dir", output_tests, fileByHash])

    assert os.path.exists(expected_file)
    with open(expected_file, "r") as f:
        expected_witness_list = json.load(f)

    assert len(expected_witness_list) == 2
    assert expected_witness_list[0]["programhash"] == program_hash
    assert expected_witness_list[1]["program-sha256"] == program_hash
