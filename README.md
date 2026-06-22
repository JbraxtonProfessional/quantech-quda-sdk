# QUDA

**Quantum Unified Device Architecture**

*Just as CUDA defined the GPU era, QUDA defines the quantum era.*

---

## What is QUDA?

QUDA is a universal quantum programming SDK for Python. Write quantum programs once and run them on any supported backend — simulator, IBM, Google, or IonQ — without rewriting your code for each platform's native API.

QUDA is hardware-agnostic by design. A single `Circuit` compiles to backend-specific instructions through the Hardware Abstraction Layer (HAL). Post-quantum security is provided via [Enclave](https://enclave.dev) encryption decorators. Execution intelligence and optimization flow through [Panoptic](https://panoptic.dev) telemetry integration.

## Quickstart

```bash
pip install quda-sdk
```

```python
import quda

@quda.target(hardware='simulator')
def bell_state():
    circuit = quda.Circuit(name="bell_state")
    field = circuit.field(size=2)

    field[0].superpose()
    field[0].entangle(field[1])

    return circuit.measure()

result = bell_state()
print(result)  # (0, 0) or (1, 1) — never (0, 1) or (1, 0)
```

No credentials. No external dependencies. Runs immediately.

Install backend extras as needed:

```bash
pip install quda-sdk[ibm]      # IBM Quantum
pip install quda-sdk[google]   # Google Cirq
pip install quda-sdk[ionq]     # IonQ trapped ion
pip install quda-sdk[all]      # All backends
```

## Backends

| Backend | Hardware | Credentials |
|---------|----------|-------------|
| `simulator` | QUDA native statevector | None |
| `ibm` | IBM Quantum / Aer | Optional — `QUDA_IBM_TOKEN` |
| `google` | Google Cirq / Quantum AI | Optional — `QUDA_GOOGLE_PROJECT_ID` |
| `ionq` | IonQ trapped ion | Optional — `QUDA_IONQ_API_KEY` |

Route execution with a single decorator:

```python
@quda.target(hardware='ibm')
def my_program():
    ...
```

Without credentials, cloud backends fall back to their local simulators automatically.

## Core Concepts

QUDA models quantum programs with three composable objects — analogous to CUDA's kernel, block, and thread hierarchy.

### State

The fundamental unit of quantum execution. A `State` exists in superposition until measured.

```python
circuit = quda.Circuit()
field = circuit.field(size=1)
field[0].superpose()          # Place into superposition
result = circuit.measure()    # Collapse to (0,) or (1,)
```

### Field

A named group of `State` objects that can interact and entangle freely.

```python
circuit = quda.Circuit()
field = circuit.field(size=4)
field.superpose_all().entangle_chain()
```

### Circuit

The execution context for all quantum operations. Owns States and Fields, compiles operations, and dispatches to the configured backend.

```python
@quda.target(hardware='simulator')
def ghz_state():
    circuit = quda.Circuit(name="ghz")
    field = circuit.field(size=4)
    field[0].superpose()
    field.entangle_all()
    return circuit.shots(1024).measure()
```

## The Decorator Stack

QUDA programs compose three decorators that connect to the full Quantech ecosystem:

```python
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
```

| Decorator | Purpose |
|-----------|---------|
| `@quda.secure` | Enclave post-quantum encryption for inputs, outputs, and execution metadata |
| `@quda.target` | Hardware backend routing via the HAL |
| `@quda.telemetry` | Panoptic intelligence — metrics, circuit structure, outcome distributions |

## The Ecosystem

QUDA sits at the center of a three-company flywheel built for the quantum era.

**Quantech** builds the hardware and the SDK. QUDA is Quantech's universal programming layer — the interface developers use to write quantum software today and run it on Quantech native hardware tomorrow.

**Enclave** provides post-quantum security. The `@quda.secure` decorator wraps program execution in Enclave's encryption infrastructure, protecting quantum workloads against classical and quantum adversaries.

**Panoptic** provides execution intelligence. The `@quda.telemetry` decorator streams circuit structure, performance metrics, and outcome distributions to Panoptic for analysis, optimization, and aggregate quantum intelligence.

## Roadmap

| Version | Milestone |
|---------|-----------|
| **v0.1** | Core SDK, simulator, IBM, Google, IonQ ✓ |
| **v0.2** | Amazon Braket backend, QUDA Cloud beta |
| **v0.3** | Panoptic telemetry live, Enclave encryption live |
| **v0.4** | Native gate optimization per backend |
| **v1.0** | Quantech native hardware |

## Contributing

QUDA is open to contributors. If you want to add a backend, improve the simulator, or extend the API, open an issue or submit a pull request on [GitHub](https://github.com/JbraxtonProfessional/quantech-quda-sdk/issues).

## License

Apache 2.0 — Copyright Quantech
