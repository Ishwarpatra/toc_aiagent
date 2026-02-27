import csv
from collections import defaultdict

data = list(csv.DictReader(open('validation_results.csv')))
total = len(data)

# Count by status
statuses = defaultdict(int)
for r in data:
    statuses[r['status']] += 1

print("\n" + "=" * 50)
print("  500 TEST VALIDATION RESULTS")
print("=" * 50)
print(f"  Total:        {total}")
print(f"  PASS:         {statuses['PASS']} ({100*statuses['PASS']/total:.1f}%)")
print(f"  FAIL:         {statuses['FAIL']}")
print(f"  ORACLE_FAIL:  {statuses['ORACLE_FAIL']} ({100*statuses['ORACLE_FAIL']/total:.1f}%)")
print(f"  ERROR:        {statuses['ERROR']}")
print("=" * 50)

# Category breakdown
print("\nCATEGORY BREAKDOWN:")
print("-" * 55)

cats = defaultdict(lambda: {'pass': 0, 'oracle': 0, 'total': 0})
for r in data:
    cat = r['category']
    cats[cat]['total'] += 1
    if r['status'] == 'PASS':
        cats[cat]['pass'] += 1
    elif r['status'] == 'ORACLE_FAIL':
        cats[cat]['oracle'] += 1

for cat in sorted(cats.keys()):
    c = cats[cat]
    rate = 100 * c['pass'] / c['total'] if c['total'] > 0 else 0
    icon = "[OK]" if c['oracle'] == 0 else "[!!]"
    print(f"  {icon} {cat[:28]:28} {c['pass']:3}/{c['total']:3} ({rate:5.1f}%) Oracle:{c['oracle']:3}")

print("\n" + "=" * 50)
if statuses['ORACLE_FAIL'] > 0:
    print("  WARNING: Oracle failures indicate Analyst misinterpretation")
    print("  Run: python retrain_analyst.py --markdown")
print("=" * 50)
