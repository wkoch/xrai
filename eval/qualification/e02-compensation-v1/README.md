# E02 compensation inventory v1

Frozen bounded selection audit, not a replacement allocation/admission profile.
Eight already qualified dossiers + four frozen state tasks, all 32 v2 slots.
`freeze.json` predates the new algorithm and pins 43 data/source inputs.

```sh
python3 eval/scripts/e02_compensation.py --inventory eval/qualification/e02-compensation-v1/inventory.json
python3 -m unittest discover -s eval/scripts -p test_e02_compensation.py
```

Both commands read captured data only; no native/upstream binary, provider,
network acquisition, historical probe or imported upstream module runs.
The first command recomputes the complete inventory before comparing it.

Results: 384 candidate/slot pairs, 12 compatible pairs, zero demonstrated
compensations within this scope. Existing eligible tasks already occupy
multimodule targets. Single-file/presence-only state tasks do not qualify
necessary cross-unit relations. Captured JS/Python literal witnesses are
retained with zero qualification credit.

The deficit remains 19/20, eight previously eligible, zero new eligible,
zero admitted. No claim that the complete repositories contain no other
natural candidate. Selection and independent qualification of such a task,
followed by an evidenced prospective allocation revision, remain pending.
