# Contributing to QUDA

Thank you for your interest in QUDA. This project is open to contributors — whether you're fixing a bug, adding a backend, improving docs, or extending the core API.

## Getting Started

1. Fork the repository on [GitHub](https://github.com/JbraxtonProfessional/quantech-quda-sdk).
2. Clone your fork locally.
3. Install in editable mode with the backends you need:

```bash
pip install -e ".[all]"
```

4. Run the test suite:

```bash
python test_quda.py
```

All 18 tests should pass. The simulator backend requires no credentials or external dependencies.

## Ways to Contribute

**Report bugs** — Open an [issue](https://github.com/JbraxtonProfessional/quantech-quda-sdk/issues) with steps to reproduce, expected behavior, and actual behavior.

**Suggest features** — Open an issue describing the use case. Check the [roadmap](README.md#roadmap) first to see if it's already planned.

**Submit code** — Open a pull request against `main`. Keep PRs focused: one feature or fix per PR.

**Add a backend** — New hardware backends belong in `quda/hal/`. Follow the pattern in `ibm.py`, `google.py`, or `ionq.py`: implement `execute`, `execute_single`, `_translate`, and `_format_results`, then register in `quda/hal/__init__.py` behind a `try/except ImportError` block.

## Pull Request Guidelines

- Match the existing code style — clear docstrings, consistent naming, minimal scope.
- Do not commit API keys, tokens, or credentials. Use environment variables (`QUDA_*`) for all secrets.
- Add tests to `test_quda.py` for new behavior. Follow the existing pattern with `@quda.target(hardware='...')`.
- Update `README.md` if your change affects install steps, backends, or public API.
- Ensure `python test_quda.py` passes before submitting.

## Code Structure

```
quda/
├── circuit.py       # Execution context — compiles and dispatches programs
├── state.py         # Fundamental quantum unit
├── field.py         # Groups of States
├── decorators.py    # @secure, @target, @telemetry
└── hal/             # Hardware Abstraction Layer
    ├── simulator.py # Built-in statevector simulator
    ├── ibm.py       # IBM Quantum / Qiskit
    ├── google.py    # Google Cirq
    └── ionq.py      # IonQ trapped ion
```

The internal import is always `import quda`. The PyPI package name is `quda-sdk`.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
