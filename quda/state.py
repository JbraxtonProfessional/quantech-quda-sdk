"""
QUDA State — The Fundamental Unit of Quantum Execution

A State is to QUDA what a Thread is to CUDA.
It is the smallest meaningful unit of quantum execution.

States only exist inside a Circuit. A State without a Circuit
has no quantum context and cannot be created.
"""

from enum import Enum


class StateStatus(Enum):
    """The lifecycle of a quantum State."""
    CLASSICAL   = "classical"     # Initialized, not yet in superposition
    SUPERPOSED  = "superposed"    # In superposition — exists in multiple values
    ENTANGLED   = "entangled"     # Entangled with one or more other States
    COLLAPSED   = "collapsed"     # Measured — superposition resolved


class State:
    """
    A single quantum information stream inside a QUDA Circuit.

    A State exists in superposition until measured — holding all
    possible values simultaneously, weighted by probability amplitudes.
    Measurement collapses the State into a single classical value.

    States are created by Circuit and Field — never directly.

    Example:
        circuit = quda.Circuit()
        field = circuit.field(size=2)

        field[0].superpose()
        field[0].entangle(field[1])
        result = circuit.measure()
    """

    def __init__(self, circuit, index: int, name: str = None):
        """
        States are created by Circuit or Field — not directly by developers.

        Args:
            circuit: The Circuit this State belongs to
            index:   The position of this State in the Circuit
            name:    Optional human-readable name for debugging
        """
        self._circuit     = circuit
        self._index       = index
        self._name        = name or f"s{index}"
        self._status      = StateStatus.CLASSICAL
        self._entangled   = []        # Other States this State is entangled with
        self._operations  = []        # Operation log for the HAL compiler
        self._value       = None      # Classical value after collapse

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def index(self) -> int:
        return self._index

    @property
    def status(self) -> StateStatus:
        return self._status

    @property
    def is_superposed(self) -> bool:
        return self._status == StateStatus.SUPERPOSED

    @property
    def is_entangled(self) -> bool:
        return self._status == StateStatus.ENTANGLED

    @property
    def is_collapsed(self) -> bool:
        return self._status == StateStatus.COLLAPSED

    @property
    def value(self):
        """The classical value of this State after collapse. None until measured."""
        return self._value

    # ── Core Quantum Operations ────────────────────────────────────────────

    def superpose(self):
        """
        Place this State into superposition.

        In superposition, a State exists in all possible values simultaneously
        — weighted by equal probability amplitudes (Hadamard gate).

        A State must be in CLASSICAL status to enter superposition.

        Returns:
            self — enables method chaining: state.superpose().entangle(other)
        """
        self._assert_not_collapsed("superpose")
        self._assert_circuit_open()

        self._status = StateStatus.SUPERPOSED
        self._operations.append({
            "op": "H",                  # Hadamard gate
            "target": self._index,
            "description": f"{self._name} → superposition"
        })
        return self

    def entangle(self, *others):
        """
        Entangle this State with one or more other States.

        Entanglement correlates States — measuring one instantly determines
        the others, regardless of physical distance.

        This State must be in SUPERPOSED status before entangling.
        Target States must belong to the same Circuit.

        Args:
            *others: One or more States to entangle with

        Returns:
            self — enables method chaining

        Example:
            field[0].superpose().entangle(field[1])
            field[0].superpose().entangle(field[1], field[2])  # Multi-entangle
        """
        self._assert_not_collapsed("entangle")
        self._assert_circuit_open()

        if self._status not in (StateStatus.SUPERPOSED, StateStatus.ENTANGLED):
            raise QUDAStateError(
                f"State '{self._name}' must be in superposition before entangling. "
                f"Call .superpose() first."
            )

        for other in others:
            self._assert_same_circuit(other)
            self._assert_not_collapsed_other(other, "entangle")

            # CNOT gate for two States, Toffoli for three
            gate = "CNOT" if len(others) == 1 else "TOFFOLI"

            self._operations.append({
                "op": gate,
                "control": self._index,
                "target": other._index,
                "description": f"{self._name} ⟷ {other._name}"
            })

            # Update entanglement registry on both States
            if other not in self._entangled:
                self._entangled.append(other)
            if self not in other._entangled:
                other._entangled.append(self)
                other._status = StateStatus.ENTANGLED

        self._status = StateStatus.ENTANGLED
        return self

    def flip(self):
        """
        Apply a Pauli-X (NOT) gate to this State.

        Flips the State: |0⟩ → |1⟩, |1⟩ → |0⟩
        In superposition, rotates the probability amplitudes.

        Returns:
            self — enables method chaining
        """
        self._assert_not_collapsed("flip")
        self._assert_circuit_open()

        self._operations.append({
            "op": "X",
            "target": self._index,
            "description": f"{self._name} → flip (Pauli-X)"
        })
        return self

    def phase(self):
        """
        Apply a Pauli-Z (phase) gate to this State.

        Flips the phase of the |1⟩ component: |0⟩ → |0⟩, |1⟩ → -|1⟩
        Used in interference and phase-based algorithms.

        Returns:
            self — enables method chaining
        """
        self._assert_not_collapsed("phase")
        self._assert_circuit_open()

        self._operations.append({
            "op": "Z",
            "target": self._index,
            "description": f"{self._name} → phase (Pauli-Z)"
        })
        return self

    def measure(self):
        """
        Collapse this State into a classical value.

        Measurement forces a quantum State to resolve its superposition
        into a single definite value: 0 or 1. This is irreversible.

        Collapse is governed by the Born rule — the probability of each
        outcome is the square of the corresponding probability amplitude.

        Returns:
            int: 0 or 1 — the classical result of measurement

        Note:
            For measuring all States in a Circuit simultaneously,
            use circuit.measure() instead.
        """
        self._assert_circuit_open()

        self._operations.append({
            "op": "MEASURE",
            "target": self._index,
            "description": f"{self._name} → collapse"
        })

        # Delegate actual execution to the circuit's backend
        result = self._circuit._execute_single(self)
        self._value = result
        self._status = StateStatus.COLLAPSED
        return result

    # ── Inspection ────────────────────────────────────────────────────────

    def ops(self) -> list:
        """Return the operation log for this State — used by the HAL compiler."""
        return self._operations.copy()

    def __repr__(self):
        entangled_names = [s._name for s in self._entangled]
        entangled_str = f" ⟷ [{', '.join(entangled_names)}]" if entangled_names else ""
        value_str = f" = {self._value}" if self._value is not None else ""
        return f"<State '{self._name}' [{self._status.value}]{entangled_str}{value_str}>"

    # ── Internal Guards ────────────────────────────────────────────────────

    def _assert_not_collapsed(self, op: str):
        if self._status == StateStatus.COLLAPSED:
            raise QUDAStateError(
                f"Cannot apply '{op}' to State '{self._name}' — "
                f"it has already collapsed. Collapse is irreversible."
            )

    def _assert_not_collapsed_other(self, other, op: str):
        if other._status == StateStatus.COLLAPSED:
            raise QUDAStateError(
                f"Cannot '{op}' with State '{other._name}' — "
                f"it has already collapsed."
            )

    def _assert_circuit_open(self):
        if self._circuit._closed:
            raise QUDAStateError(
                f"Circuit is closed. No operations can be applied after measurement."
            )

    def _assert_same_circuit(self, other):
        if other._circuit is not self._circuit:
            raise QUDAStateError(
                f"Cannot entangle State '{self._name}' with State '{other._name}' "
                f"— they belong to different Circuits. "
                f"States can only entangle within the same Circuit."
            )


# ── Exceptions ────────────────────────────────────────────────────────────

class QUDAStateError(Exception):
    """Raised when an invalid operation is attempted on a State."""
    pass
