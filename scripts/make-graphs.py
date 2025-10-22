#!/usr/bin/python3

import pandas as pd
import matplotlib.pyplot as plt

def make_graphs(data_file, name):
    # Load data
    data = pd.read_csv(data_file)

    solvers = ['a-str', 'cvc5', 'ostrich', 'z3-noodler']
    cum_a-str = data['a-str_time'].cumsum()
    cum_cvc5 = data['cvc5_time'].cumsum()
    cum_ostrich = data['ostrich_time'].cumsum()
    cum_z3 = data['z3-noodler_time'].cumsum()
    x = range(1, len(data) + 1)

    plt.figure(figsize=(10,6))
    plt.plot(x, cum_a-str, label='a-str')
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
    make_graphs('../results/smt-results.csv', 'SMT')
    make_graphs('../results/real-results.csv', 'Real')
