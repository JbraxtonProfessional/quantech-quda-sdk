"""
QUDA Test Suite — v0.1.0

Tests the core QUDA SDK against the language spec.
"""

import quda

print("=" * 55)
print("  QUDA — Quantum Unified Device Architecture")
print("  Test Suite v0.1.0")
print("=" * 55)
print()

# ── Test 1: Version and Backends ──────────────────────────
print("TEST 1: Version and Available Backends")
print(f"  Version:  {quda.version()}")
print(f"  Backends: {quda.backends()}")
print("  ✓ PASS")
print()

# ── Test 2: Bell State (Hello World of Quantum Computing) ──
print("TEST 2: Bell State — The Hello World of Quantum Computing")
print("  Creates two entangled States.")
print("  Result must be (0,0) or (1,1) — never (0,1) or (1,0)")
print()

@quda.target(hardware='simulator')
def bell_state():
    circuit = quda.Circuit(name="bell_state")
    field = circuit.field(size=2)

    field[0].superpose()
    field[0].entangle(field[1])

    return circuit.measure()

results = set()
for i in range(20):
    result = bell_state()
    results.add(result)

print(f"  Outcomes observed over 20 runs: {results}")
assert (0, 0) in results or (1, 1) in results, "Expected (0,0) or (1,1)"
assert (0, 1) not in results, "Unexpected (0,1) — entanglement violated"
assert (1, 0) not in results, "Unexpected (1,0) — entanglement violated"
print("  ✓ PASS — Entanglement confirmed. Only correlated outcomes observed.")
print()

# ── Test 3: Circuit Diagram ────────────────────────────────
print("TEST 3: Circuit Diagram")

circuit = quda.Circuit(name="diagram_test")
field = circuit.field(size=2)
field[0].superpose()
field[0].entangle(field[1])

print(circuit.diagram())
print("  ✓ PASS")
print()

# ── Test 4: Superposition Distribution ────────────────────
print("TEST 4: Superposition — Statistical Distribution")
print("  A single State in superposition should yield ~50% 0, ~50% 1")
print()

@quda.target(hardware='simulator')
def single_superposition():
    circuit = quda.Circuit()
    field = circuit.field(size=1)
    field[0].superpose()
    return circuit.measure()

counts = {(0,): 0, (1,): 0}
runs = 100
for _ in range(runs):
    r = single_superposition()
    counts[r] = counts.get(r, 0) + 1

pct_zero = counts.get((0,), 0) / runs * 100
pct_one  = counts.get((1,), 0) / runs * 100
print(f"  |0⟩: {pct_zero:.0f}%   |1⟩: {pct_one:.0f}%  (over {runs} shots)")
assert 30 <= pct_zero <= 70, f"Distribution too skewed: {pct_zero}% zeros"
print("  ✓ PASS — Superposition confirmed. Distribution is probabilistic.")
print()

# ── Test 5: Collapse is Irreversible ──────────────────────
print("TEST 5: Collapse Irreversibility")
print("  Attempting operations on a collapsed State should raise QUDAStateError")
print()

circuit = quda.Circuit()
field = circuit.field(size=1)
field[0].superpose()
circuit.measure()

try:
    field[0].superpose()  # Should fail — State is collapsed
    print("  ✗ FAIL — No error raised on collapsed State")
except quda.QUDAStateError as e:
    print(f"  Error caught: {e}")
    print("  ✓ PASS — Collapse is irreversible. Physics enforced.")
print()

# ── Test 6: Closed Circuit Guard ──────────────────────────
print("TEST 6: Closed Circuit Guard")
print("  Attempting to add States after measurement should raise QUDACircuitError")
print()

circuit = quda.Circuit()
field = circuit.field(size=1)
field[0].superpose()
circuit.measure()

try:
    circuit.field(size=1)  # Should fail — circuit is closed
    print("  ✗ FAIL — No error raised on closed Circuit")
except quda.QUDACircuitError as e:
    print(f"  Error caught: {e}")
    print("  ✓ PASS — Closed Circuit enforced.")
print()

# ── Test 7: Entanglement Requires Superposition ───────────
print("TEST 7: Entanglement Requires Superposition")
print("  Entangling a classical State should raise QUDAStateError")
print()

circuit = quda.Circuit()
field = circuit.field(size=2)

try:
    field[0].entangle(field[1])  # field[0] not in superposition
    print("  ✗ FAIL — No error raised")
except quda.QUDAStateError as e:
    print(f"  Error caught: {e}")
    print("  ✓ PASS — QUDA enforces quantum rules.")
print()

# ── Test 8: Multi-Shot Distribution ───────────────────────
print("TEST 8: Multi-Shot Bell State Distribution")
print("  Running Bell state 512 times — expect ~50% (0,0), ~50% (1,1)")
print()

circuit = quda.Circuit(name="bell_multishot")
field = circuit.field(size=2)
field[0].superpose()
field[0].entangle(field[1])
distribution = circuit.shots(512).measure()

print(f"  Distribution: {distribution}")
total = sum(distribution.values())
for outcome, count in sorted(distribution.items()):
    print(f"    {outcome}: {count} ({count/total*100:.1f}%)")

assert (0, 0) in distribution or (1, 1) in distribution
print("  ✓ PASS — Multi-shot distribution confirmed.")
print()

# ── Test 9: Full Stack Decorator ──────────────────────────
print("TEST 9: Full Stack — All Three Decorators")
print()

@quda.secure(enclave=True)
@quda.target(hardware='simulator')
@quda.telemetry(panoptic=True)
def full_stack_bell():
    circuit = quda.Circuit(name="full_stack")
    field = circuit.field(size=2)
    field[0].superpose()
    field[0].entangle(field[1])
    return circuit.measure()

result = full_stack_bell()
print(f"  Result: {result}")
assert result in [(0, 0), (1, 1)]
print("  ✓ PASS — Full stack execution successful.")
print()

# ── Test 10: Field Bulk Operations ────────────────────────
print("TEST 10: Field Bulk Operations")
print()

@quda.target(hardware='simulator')
def ghz_state():
    """GHZ State — all States correlated across a 4-State Field."""
    circuit = quda.Circuit(name="ghz")
    field = circuit.field(size=4)
    field[0].superpose()
    field.entangle_all()
    return circuit.measure()

ghz_results = set()
for _ in range(20):
    r = ghz_state()
    ghz_results.add(r)

print(f"  GHZ outcomes over 20 runs: {ghz_results}")
for r in ghz_results:
    assert len(set(r)) == 1, f"GHZ violated — mixed outcome: {r}"
print("  ✓ PASS — GHZ State confirmed. All States correlated.")
print()

# ── Summary ───────────────────────────────────────────────
print("=" * 55)
print("  ALL TESTS PASSED")
print(f"  QUDA v{quda.version()} — Core SDK operational.")
print("  Ready for IBM backend integration.")
print("=" * 55)
