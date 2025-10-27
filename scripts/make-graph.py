#!.venv/bin/python3

import pandas as pd
import matplotlib.pyplot as plt
import argparse
import os

def make_graph(data_file, name):
    data = pd.read_csv(data_file)

    solvers = ['a-str', 'cvc5', 'ostrich', 'z3-noodler']
    cum_a_str = data['a-str_time'].cumsum()
    cum_cvc5 = data['cvc5_time'].cumsum()
    cum_ostrich = data['ostrich_time'].cumsum()
    cum_z3 = data['z3-noodler_time'].cumsum()
    x = range(1, len(data) + 1)

    plt.figure(figsize=(10,6))
    plt.plot(x, cum_a_str, label='a-str')
    plt.plot(x, cum_cvc5, label='CVC5')
    plt.plot(x, cum_ostrich, label='Ostrich')
    plt.plot(x, cum_z3, label='Z3-Noodler')
    plt.xlabel('Benchmarks completed')
    plt.ylabel('Cumulative time (s)')
    plt.title('Cumulative ' + name + ' Solver Times')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'results/{name}_graph.png')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make solver time graphs.")
    parser.add_argument("data_file", help="CSV file with results")
    parser.add_argument("name", help="Name for the graph")
    args = parser.parse_args()
    if not args.data_file or not args.name:
        parser.print_help()
        exit(1)
    if not os.path.isfile(args.data_file):
        print(f"Error: {args.data_file} does not exist.")
        exit(1)
    make_graph(args.data_file, args.name)
