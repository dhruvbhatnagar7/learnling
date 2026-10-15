"""Split an eval output table by case kind and child age.

    python eval/breakdown.py results/2026-10-13/child-vosk.txt
"""
import re, sys, collections
rows = collections.defaultdict(lambda: [0, 0, 0, 0])  # correct words, false, errors, caught
for line in open(sys.argv[1]):
    m = re.match(r'(c\d+-age(\d+)-\S+?-(clean|close|different|skip))\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', line)
    if not m: continue
    _, age, kind, words, errors, caught, missed, false = m.groups()
    words, errors, caught, false = map(int, (words, errors, caught, false))
    for key in (f'kind {kind}', f'age {age}'):
        r = rows[key]; r[0] += words - errors; r[1] += false; r[2] += errors; r[3] += caught
for k in sorted(rows):
    c, f, e, ca = rows[k]
    print(f"{k:<16} false {f}/{c} = {f/c:.0%}" + (f"   caught {ca}/{e} = {ca/e:.0%}" if e else ''))
