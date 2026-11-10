"""Optional independent symbolic algebra reference; not a support verifier."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp
from tools.response_cases import differential_cases
from absorblab.response import analyze_response


def main():
    delta = sp.Symbol('delta')
    counts = {'requests': 0, 'probability_curves': 0, 'derivative_pairs': 0}
    for request in differential_cases():
        report = analyze_response(request)
        names = report['names']
        us = report['anchor']['transient_indices']
        n = len(names)
        raw = [[sp.Rational(0) for _ in names] for _ in names]
        for i, state in enumerate(request['chain']['states']):
            for edge in state['transitions']:
                raw[i][names.index(edge['to'])] = sp.Rational(edge['prob'])
        row, donor, receiver = [names.index(request[k]) for k in ('row', 'donor', 'receiver')]
        t = sp.Rational(report['domain']['anchor']) + delta
        raw[row][donor] -= t
        raw[row][receiver] += t
        matrix = sp.Matrix([[int(i == j) - raw[i][j] for j in us] for i in us]) if us else sp.zeros(0)
        denominator = sum(sp.Rational(v) * delta ** k for k, v in enumerate(report['response']['denominator']))
        for key in ('success', 'failure'):
            boundary = {names.index(x) for x in request['chain'][key]}
            rhs = sp.Matrix([sum(raw[i][j] for j in boundary) for i in us]) if us else sp.zeros(0, 1)
            solved = matrix.inv() * rhs if us else sp.zeros(0, 1)
            for i in range(n):
                value = solved[us.index(i)] if i in us else sp.Integer(i in boundary)
                numerator = sum(sp.Rational(v) * delta ** k for k, v in enumerate(report['response']['curves'][i][key]))
                formula = numerator / denominator
                assert sp.cancel(value - formula) == 0
                counts['probability_curves'] += 1
                for point in report['samples']:
                    if not point['interior']:
                        continue
                    where = sp.Rational(point['transfer']) - sp.Rational(report['domain']['anchor'])
                    expected = point['derivatives'][i][key]
                    assert sp.cancel(sp.diff(value, delta).subs(delta, where)) == sp.Rational(expected['first'])
                    assert sp.cancel(sp.diff(value, delta, 2).subs(delta, where)) == sp.Rational(expected['second'])
                    counts['derivative_pairs'] += 1
        counts['requests'] += 1
    print(json.dumps({'sympy': sp.__version__, 'scope': 'Symbolic algebra on the supplied interior transient indices; separate checker owns support correctness.', **counts}))


if __name__ == '__main__':
    main()
