"""
QUDA Field — A Collection of States

A Field is a named group of States within a Circuit.
It defines the scope of interaction — States within the same
Field can freely entangle with each other.

Analogous to a Block in CUDA — a group of Threads that can
share memory and communicate directly.
"""

from .state import State, QUDAStateError


class Field:
    """
    A collection of quantum States within a Circuit.

    Fields organize States into logical groups. All States in a Field
    share the same quantum context and can entangle freely.

    Fields are created by Circuit — never directly.

    Example:
        circuit = quda.Circuit()

        # Create a field of 4 states
        field = circuit.field(size=4)

        # Access states by index
        field[0].superpose()
        field[0].entangle(field[1])

        # Superpose all states at once
        field.superpose_all()

        result = circuit.measure()
    """

    def __init__(self, circuit, size: int, name: str = None, index_offset: int = 0):
        """
        Fields are created by Circuit — not directly by developers.

        Args:
            circuit:        The Circuit this Field belongs to
            size:           Number of States in this Field
            name:           Optional human-readable name
            index_offset:   Starting index for States (for multi-field Circuits)
        """
        self._circuit      = circuit
        self._size         = size
        self._name         = name or f"field{index_offset}"
        self._index_offset = index_offset

        # Create States — bound to this Circuit
        self._states = [
            State(circuit, index=index_offset + i, name=f"{self._name}.s{i}")
            for i in range(size)
        ]

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def size(self) -> int:
        return self._size

    @property
    def states(self) -> list:
        return self._states.copy()

    # ── Access ────────────────────────────────────────────────────────────

    def __getitem__(self, index: int) -> State:
        """Access a State by index: field[0], field[1], etc."""
        if index < 0 or index >= self._size:
            raise QUDAFieldError(
                f"Field '{self._name}' has {self._size} States (indices 0–{self._size - 1}). "
                f"Index {index} is out of range."
            )
        return self._states[index]

    def __len__(self) -> int:
        return self._size

    def __iter__(self):
        return iter(self._states)

    # ── Bulk Operations ───────────────────────────────────────────────────

    def superpose_all(self):
        """
        Place all States in this Field into superposition simultaneously.

        Equivalent to calling .superpose() on each State individually.
        This is the standard starting point for most quantum algorithms.

        Returns:
            self — enables method chaining
        """
        for state in self._states:
            state.superpose()
        return self

    def entangle_chain(self):
        """
        Entangle States in a linear chain: s0 ⟷ s1 ⟷ s2 ⟷ ... ⟷ sN

        All States must be in superposition before chaining.
        Creates a chain of pairwise entanglement across the Field.

        Returns:
            self — enables method chaining

        Example:
            field.superpose_all().entangle_chain()
        """
        for i in range(self._size - 1):
            self._states[i].entangle(self._states[i + 1])
        return self

    def entangle_all(self):
        """
        Entangle the first State with all others in the Field.

        Creates a star topology — s0 entangled with s1, s2, ... sN.
        s0 must be in superposition first.

        Returns:
            self — enables method chaining

        Example:
            field[0].superpose()
            field.entangle_all()
        """
        control = self._states[0]
        targets = self._states[1:]
        for target in targets:
            control.entangle(target)
        return self

    def flip_all(self):
        """Apply Pauli-X (NOT) to all States in this Field."""
        for state in self._states:
            state.flip()
        return self

    # ── Inspection ────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return the status of all States in this Field."""
        return {state.name: state.status.value for state in self._states}

    def __repr__(self):
        state_summary = ", ".join(s.status.value for s in self._states)
        return f"<Field '{self._name}' [{self._size} states: {state_summary}]>"


# ── Exceptions ────────────────────────────────────────────────────────────

class QUDAFieldError(Exception):
    """Raised when an invalid operation is attempted on a Field."""
    pass
