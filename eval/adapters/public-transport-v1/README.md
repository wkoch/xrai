# Public fake transport profile v1

Prospective local-only profile. The concrete consumer in `prove.py` calls one
`PublicTransportSession`, whose financial authority is the inherited, unchanged
D01 `_State`. The historical adapter, immutable v4 and consumer v3 are unchanged.
No second ledger/authority, runtime profiler, real provider, native executable,
upstream import or campaign runs here.

Final wire bytes use `xrai.eval.fake-transport-wire.v1`: the canonical logical
request inside a versioned JSON envelope plus LF. Both representations and their
separate hashes/sizes are retained before reservation and commitment. Public
`PublicFakeTransport.send` emits an entry receipt from the exact bytes it receives,
with task/arm/run/call/attempt/commit identities. Receipt bytes are checked live and
on replay. A local entry proves local fake consumption only; remote delivery,
model execution, real tokens and provider charge remain unknown.

`record()` returns an explicit incomplete snapshot including active operations;
`record(close=True)` refuses while any capture/transport operation is active.
`replay_public_transport(record)` requires closure by default. Late responses and
synthetic financial receipts are idempotent, bound to their original attempt;
uncertain commitments retain reservation. A planned public pre-entry policy
refusal occurs before reserve/commit and provides factual absence.

Limits: 16 requests including pending/refused requests, 128 public events,
128 KiB per logical/wire/response byte object, 16 MiB replay record/proof. These
are byte limits, not token measurements. The inherited authorization is the only
financial allowance; retries share its cumulative costs/reservations.

```sh
python3 -m unittest discover -s crates/xrai-eval/harness/tests -p test_transport_receipt_session.py -v
python3 eval/adapters/public-transport-v1/verify.py
```

`prove.py --output PATH` creates new fake evidence; verification is read-only.
The retained proof has eight records (seven closed plus one live snapshot).
Python 3.15.0 was used locally; CI Python 3.13 is a separate pending verification.
The Store binding/consumer bridge, monotonic ABA fencing and blobs are future
work. Construction uses the historical base's private built-in fake adapter only
to initialize its existing financial state; that adapter is never invoked.
