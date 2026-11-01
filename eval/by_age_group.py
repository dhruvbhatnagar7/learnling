"""Split children's eval results into age groups, as a markdown table.

    python eval/by_age_group.py "Whisper base.en=results/2026-10-13/child-whisper.txt" ...

Groups do not overlap: under 3, 3 to 4, 5 to 7, 8 to 12. A child's age is
the one speechocean762 records for that speaker, carried in the case name
("c000-age7-1075-clean"). A group with fewer than MIN_MISTAKES real
mistakes gets its catch rate marked as unstable.
"""
import re
import sys

GROUPS = [("1-3", 0, 2), ("3-5", 3, 4), ("5-8", 5, 7), ("8-12", 8, 12)]
MIN_MISTAKES = 30
ROW = re.compile(r"(c\d+-age(\d+)-(\S+?)-(clean|close|different|skip))\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)")


def tally(path):
    groups = {name: [set(), 0, 0, 0, 0] for name, _, _ in GROUPS}  # children, correct words, false, mistakes, caught
    total = [set(), 0, 0, 0, 0]
    for line in open(path):
        m = ROW.match(line)
        if not m:
            continue
        _, age, speaker, _, words, errors, caught, _, false = m.groups()
        age, words, errors, caught, false = map(int, (age, words, errors, caught, false))
        name = next(n for n, lo, hi in GROUPS if lo <= age <= hi)
        for r in (groups[name], total):
            r[0].add(speaker)
            r[1] += words - errors
            r[2] += false
            r[3] += errors
            r[4] += caught
    return groups, total


def rate(a, b):
    return f"{a / b:.1%}"


print("| Model | Age group | Children | Correct words | Real mistakes | Correct words wrongly flagged | Mistakes caught |")
print("|---|---|---|---|---|---|---|")
for spec in sys.argv[1:]:
    label, path = spec.split("=", 1)
    groups, total = tally(path)
    for name, _, _ in GROUPS:
        children, correct, false, mistakes, caught = groups[name]
        if not children:
            print(f"| {label} | {name} | 0 | no data | no data | no data | no data |")
            continue
        catch = rate(caught, mistakes) + (" (too few mistakes)" if mistakes < MIN_MISTAKES else "")
        print(f"| {label} | {name} | {len(children)} | {correct} | {mistakes} | {rate(false, correct)} | {catch} |")
    children, correct, false, mistakes, caught = total
    print(f"| {label} | all | {len(children)} | {correct} | {mistakes} | {rate(false, correct)} | {rate(caught, mistakes)} |")
