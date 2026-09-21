import sys
sys.path.insert(0, '.')
from src.interactive.scaffolder import InteractiveScaffolder, TopologyEngine

sc = InteractiveScaffolder()
step0 = sc.parse_and_create_step_one('Create E MS Installatie FP', use_rag=False)
print(f'Step 0: {step0["method"]} {step0["object"]}')

anchor = step0
choices = [2, 3, 4, 5]
for c in choices:
    recs = TopologyEngine.get_downstream_recommendations(anchor['object'], anchor['method'])
    print(f'  anchor=[{anchor["method"]}] {anchor["object"]}  menu_size={len(recs)} (DONE={len(recs)+1})  pick {c}:', end=' ')
    if c - 1 == len(recs):
        print('-> DONE'); break
    rec = recs[c - 1]
    print(f'-> [{rec["method"]}] {rec["object"]}')
    nxt = sc.build_cascade_step(rec, anchor)
    if rec['type'] in ('physical_cascade', 'spatial_cascade', 'cable_splice_association'):
        anchor = nxt

print(f'\nTotal generated steps: {len(sc.steps)}')
for s in sc.steps:
    print(f'  step {s["step_index"]}: {s["method"]:12} {s["object"]}')
