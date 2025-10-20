#!/usr/bin/env python3

# Call using `PYTHONPATH=benchexec:scripts ./scripts/prepare_tables/mkValidatorStatistics.py`
import prepare_tables.adjust_results_verifiers
from collections import Counter
import os
import re
import datetime
import yaml
import argparse
import sys
import logging

import benchexec.result as Result
import benchexec.tablegenerator as tablegenerator

VERIFIEDDIR = "./results-verified/"
VALIDATEDDIR = "./results-validated/"


def getLatestVerifierXML(verifier, category, competition):
    """
    example usage:
    print(getLatestVerifierXML("cpa-seq","ReachSafety"))
    """
    r = re.compile(
        verifier
        + f"\.(.?.?.?.?-.?.?-.?.?_.?.?-.?.?-.?.?)\.results\.{competition}_"
        + category.lower()
        + "\.xml\.bz2"
    )
    result = None
    date = None
    for filename in os.listdir(VERIFIEDDIR):
        m = r.match(filename)
        if m:
            newDate = datetime.datetime.strptime(m.group(1), "%Y-%m-%d_%H-%M-%S")
            if result and newDate < date:
                continue
            result = VERIFIEDDIR + filename
            date = newDate
    if result:
        return result


def getLatestWitnessXMLs(verifier, category, competition):
    """
    example usage:
    for (k,v) in getLatestWitnessXMLs("cpa-seq","ReachSafety").items():
    print("%s\n%s" % (k,v))
    """
    rval = re.compile(
        "(.*)-"
        + verifier
        + f"\.(.?.?.?.?-.?.?-.?.?_.?.?-.?.?-.?.?)\.results\.{competition}_"
        + category.lower()
        + "\.xml\.bz2"
    )
    results = dict()
    dates = dict()
    for filename in os.listdir(VALIDATEDDIR):
        m = rval.match(filename)
        if m:
            date = datetime.datetime.strptime(m.group(2), "%Y-%m-%d_%H-%M-%S")
            if m.group(1) in results and date < dates[m.group(1)]:
                continue
            results[m.group(1)] = VALIDATEDDIR + filename
            dates[m.group(1)] = date
    return results


def xmlPathToValidatorName(s):
    """
    example usage:
    s = "/results-validated/uautomizer-validate-violation-witnesses-cpa-seq.2019-12-03_0856.results.sv-comp20_prop-reachsafety.xml.bz2"
    print(xmlPathToValidatorName(s))
    """
    if not xmlPathToValidatorName.r:
        xmlPathToValidatorName.r = re.compile(".*results-validated/(.*)-witnesses-.*")
    m = xmlPathToValidatorName.r.match(s)
    if m:
        name = m.group(1)
        # The xml name is calculated from the validator name according to these three cases:
        #   1. toolname-violation -> toolname-validate-violation-witnesses.xml
        #   2. toolname-correctness -> toolname-validate-correctness-witnesses.xml
        #   3. toolname only -> toolname-validate-witnesses.xml
        # (this is taken from/ originally documented in scripts/test/_util.py)
        # In order to catch the third case, we need to do the following:
        name = "".join(name.rsplit("-validate", 1))
        return name
    else:
        return None


xmlPathToValidatorName.r = re.compile(".*results-validated/(.*)-witnesses-.*")
# TODO: extract this into proper unit tests:
assert (
    xmlPathToValidatorName(
        "/results-validated/uautomizer-validate-violation-witnesses-foo"
    )
    == "uautomizer-violation"
)
assert (
    xmlPathToValidatorName(
        "/results-validated/uautomizer-validate-correctness-witnesses-foo"
    )
    == "uautomizer-correctness"
)
assert (
    xmlPathToValidatorName("/results-validated/witnesslint-validate-witnesses-foo")
    == "witnesslint"
)


def validator_suffix(validator_name, expected_verdict):
    is_both_type_validator = not validator_name.endswith(
        "-correctness"
    ) and not validator_name.endswith("-violation")
    if is_both_type_validator:
        if expected_verdict == "true":
            suffix = "-correctness"
        elif "false" in expected_verdict:  # memsafety has "false(subproperty)" !
            suffix = "-violation"
        else:
            suffix = "-unknown"
            logger.warning(f"Unknown expected verdict: {expected_verdict}")
    else:
        suffix = ""
    return suffix


def get_runs(validator_linter_xml):
    runs = {}
    for run in validator_linter_xml.findall("run"):
        name = run.get("name")
        runs[name] = run
    return runs


def scanWitnessResults(verifier, category, property_, counter):
    competition = catdict["competition"] + str(catdict["year"])[-2:]
    resultFile = getLatestVerifierXML(verifier, property_, competition)
    if not resultFile:
        if verifier in catdict["opt_out"] and any(
            category.lower() in entry.lower() for entry in catdict["opt_out"][verifier]
        ):
            logger.info("Verifier %s opted out of category %s", verifier, category)
        else:
            logger.warning("No result for %s in category %s", verifier, category)

        return
    logger.info("Scanning result file: %s", resultFile)
    witnessFiles = getLatestWitnessXMLs(verifier, property_, competition).values()

    if not os.path.exists(resultFile) or not os.path.isfile(resultFile):
        logger.error(f"File {repr(resultFile)} does not exist")
        sys.exit(1)
    resultXML = tablegenerator.parse_results_file(resultFile)
    witnessSets = []
    for witnessFile in witnessFiles:
        if not os.path.exists(witnessFile) or not os.path.isfile(witnessFile):
            logger.error(f"File {repr(witnessFile)} does not exist")
            sys.exit(1)
        witnessXML = tablegenerator.parse_results_file(witnessFile)
        witnessSets.append(get_runs(witnessXML))

    # check for presence of validator results for every (verifier,category) in case category-structure.yml claims that the validator is validating the category
    for val in catdict["categories"][category]["validators"]:
        found = False
        for item in [
            xmlPathToValidatorName(witnessFile) for witnessFile in witnessFiles
        ]:
            if val == item:
                found = True
                break
        if not found:
            logger.warning(
                "Missing validation results with validator %s! (category:%s, verifier:%s)",
                val,
                category,
                verifier,
            )
        else:
            logger.info(
                f"Found validation results with validator {val}! (category:{category}, verifier:{verifier})"
            )

    for result in resultXML.findall("run"):
        run = result.get("name")
        expected_verdict = result.get("expectedVerdict")
        d = dict()
        for witnessSet, witnessFile in zip(witnessSets, witnessFiles):
            witness = witnessSet.get(run, None)
            validator_name = xmlPathToValidatorName(witnessFile)
            suffix = validator_suffix(validator_name, expected_verdict)
            # copy data from witness
            if witness is not None and len(witness) > 0:
                counter[
                    category + "-EXISTING_WITNESSES-" + validator_name + suffix
                ] += 1
                # For verification
                statusWitNew, categoryWitNew = (
                    prepare_tables.adjust_results_verifiers.get_validator_linter_result(
                        witness, result
                    )
                )  # for this call we need the import from adjust_results_verifiers.py
                d[witnessFile] = (statusWitNew, categoryWitNew)
                if not (
                    statusWitNew.startswith("witness invalid")
                    or statusWitNew.startswith("result invalid")
                ):
                    counter[
                        category + "-VALID_WITNESSES-" + validator_name + suffix
                    ] += 1
                # if (
                #    categoryWit is None
                #    or not categoryWit.startswith(Result.CATEGORY_CORRECT)
                #    or categoryWitNew == Result.CATEGORY_CORRECT
                #    or statusWitNew.startswith("witness invalid")
                # ):
                #    statusWit, categoryWit = (statusWitNew, categoryWitNew)
        for validator in d.keys():
            if d[validator][1] == Result.CATEGORY_CORRECT:
                unique = True
                joint = False
                for othervalidator in d.keys():
                    if (
                        othervalidator != validator
                        and d[othervalidator][1] == Result.CATEGORY_CORRECT
                    ):
                        unique = False
                        joint = True
                validator_name = xmlPathToValidatorName(validator)
                suffix = validator_suffix(validator_name, expected_verdict)
                if unique:
                    counter[
                        category + "-CONFIRMED_UNIQUE-" + validator_name + suffix
                    ] += 1
                if joint:
                    counter[
                        category + "-CONFIRMED_JOINT-" + validator_name + suffix
                    ] += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--silent", help="output no debug information", action="store_true"
    )
    parser.add_argument(
        "--category-structure",
        required=True,
        dest="category_structure",
        help="Path to the category-structure.yml",
    )
    parser.add_argument(
        "--htmlfile",
        help="file in case the statistics shall be made available as HTML document",
    )
    args = parser.parse_args()
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("mkValidatorStatistics")
    if args.silent:
        logger.setLevel(logging.ERROR)
    else:
        logger.setLevel(logging.DEBUG)

    catdict = yaml.load(
        open(args.category_structure, "r").read(), Loader=yaml.FullLoader
    )

    # remove meta-categories for now, as they do not have their own xml file:
    for entry in (
        "FalsificationOverall",
        "JavaOverall",
        "SoftwareSystems",
        "Overall",
        "ConcurrencySafety",
    ):
        del catdict["categories"][entry]

    counter = Counter()
    for category in catdict["categories"].keys():
        # hack to get the string in the xml file names which is actually the property,
        # not the category
        properties = catdict["categories"][category]["properties"]
        assert isinstance(properties, str) or len(properties) <= 2
        if not isinstance(properties, str):
            if len(properties) == 2:
                assert category == "MemSafety"
            property_ = properties[0]
        else:
            property_ = properties
        verifiers = catdict["categories"][category]["verifiers"]
        for verifier in verifiers:
            scanWitnessResults(verifier, category, property_, counter)
    tablestart = """<!DOCTYPE html>
<html>
<head>
<title>Validator Statistics</title>
<link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/4.1.3/css/bootstrap.css">
<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.20/css/dataTables.bootstrap4.min.css">
<script type="text/javascript" language="javascript" src="https://code.jquery.com/jquery-3.3.1.js"></script>
<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/1.10.20/js/jquery.dataTables.min.js"></script>
<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/1.10.20/js/dataTables.bootstrap4.min.js"></script>
<script type="text/javascript" class="init">
$(document).ready(function() {
    // Setup - add a text input to each footer cell
    $('#basic thead tr').clone(true).appendTo( '#basic thead' );
    $('#basic thead tr:eq(1) th').each( function (i) {
        var title = $(this).text();
        $(this).html( '<input type="text" placeholder="Search '+title+'" />' );
 
        $( 'input', this ).on( 'keyup change', function () {
            if ( table.column(i).search() !== this.value ) {
                table
                    .column(i)
                    .search( this.value )
                    .draw();
            }
        } );
    } );
 
    var table = $('#basic').DataTable( {
        orderCellsTop: true,
        fixedHeader: true
    } );
} );
</script>
</head>
          
<body>
        <table id="basic" class="table table-striped table-bordered" cellspacing="0" width="100%">
        <thead>
        <tr>
          <th>Category
          </th>
          <th>Violation/Correctness
          </th>
          <th>Validator
          </th>
          <th>Criterion
          </th>
          <th>Count</th>
        </tr>
      </thead>
    <tbody>

"""
    tableend = """</tbody>
</table>
</body>
</html>
"""
    if not args.htmlfile:
        sys.exit(0)
    with open(args.htmlfile, "w") as f:
        f.write(tablestart)
        for k, v in counter.items():
            m = re.compile("([a-zA-Z]*)-([A-Z\_]*)-(.*)-(.*)").match(k)
            if not m:
                logger.warning(f"No statistics found for {k}")
                continue
            category = m.group(1)
            criterion = m.group(2)
            verifier = m.group(3)
            result = m.group(4)
            f.write(
                "<tr> <td>%s</td> <td>%s</td> <td>%s</td> <td>%s</td> <td>%s</td> </tr>\n"
                % (category, result, verifier, criterion.lower(), v)
            )
        f.write(tableend)
