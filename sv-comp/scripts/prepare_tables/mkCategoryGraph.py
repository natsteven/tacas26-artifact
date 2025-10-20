#!/usr/bin/env python3

import argparse
import yaml

START_NUMBERS = 0
OVERALL = "Overall"
OVERALL_CATEGORIES = ("Overall", "FalsificationOverall", "JavaOverall")


def create_dot(comp_data) -> str:
    dot_data = [
        "digraph CATEGORIES {",
        "",
        "compound=true",
        "rankdir=LR",
        "",
        'node [style="filled" shape="box" fontname="arial" fillcolor="lightblue"]',
        'fontname="arial"',
        "",
    ]

    node_number = START_NUMBERS - 1
    node_number += 1
    dot_data.append('{} [label="{}"]'.format(node_number, OVERALL))
    overall_number = node_number
    for c, c_info in sorted(comp_data["categories"].items(), key=lambda e: e[0]):
        if c in OVERALL_CATEGORIES:
            continue
        node_number += 1
        dot_data.append('{} [label="{}"]'.format(node_number, c))
        dot_data.append("{} -> {}".format(overall_number, node_number))

        if "categories" in c_info and len(c_info["categories"]) > 1:
            dot_data.append("subgraph cluster_{} {{".format(node_number))
            dot_data.append('  label = "{}";'.format(c))
            sub_number = START_NUMBERS - 1
            for base_category in c_info["categories"]:
                sub_number += 1
                dot_data.append(
                    '  {0}{1} [label="{2}"]'.format(
                        node_number, sub_number, base_category
                    )
                )
            dot_data.append("}")

            # use this code piece if you want a single arrow from meta- to base-category
            dot_data.append("{0} -> {0}0[lhead=cluster_{0}]".format(node_number))
            # Use this code piece instead if you want an arrow to each base-category
            # for n in range(START_NUMBERS, sub_number+1):
            #     dot_data.append("{0} -> {0}{1}".format(node_number, n))
            dot_data.append("")
    dot_data.append("}")

    return "\n".join(dot_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="categories.dot",
        help="output file",
    )
    parser.add_argument(
        "category_file",
        help="category description as yaml file",
    )
    args = parser.parse_args()
    with open(args.category_file) as inp:
        category_data = yaml.load(inp, Loader=yaml.FullLoader)
    dot = create_dot(category_data)
    with open(args.output, "w") as outp:
        outp.write(dot)
