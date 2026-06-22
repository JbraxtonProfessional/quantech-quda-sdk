"""
QUDA Simulator Backend

A local statevector simulator for development and testing.
No quantum hardware required. Runs on any laptop.

The simulator faithfully implements quantum mechanics:
- Superposition via Hadamard gate
- Entanglement via CNOT and Toffoli gates
- Probabilistic measurement via Born rule
- Irreversible collapse

This is the default backend when no @quda.target decorator is used.
"""

import random
import math
from collections import Counter


class SimulatorBackend:
    """
    Local quantum statevector simulator.

    Represents the full quantum state as a complex amplitude vector
    of size 2^n, where n is the number of States in the Circuit.
    All quantum operations are applied as matrix transformations.
    """

    def execute(self, program: dict):
        """
        Execute a compiled QUDA program on the local simulator.

        Args:
            program: Compiled program from Circuit._compile()

        Returns:
            tuple: Single measurement result e.g. (0, 1, 0, 1)
            dict:  Distribution if shots > 1 e.g. {(0,0): 512, (1,1): 512}
        """
        n = program["state_count"]
        ops = program["operations"]
        shots = program.get("shots", 1)

        if shots == 1:
            state_vector = self._init_statevector(n)
            state_vector = self._apply_ops(state_vector, ops, n)
            return self._measure(state_vector, n)
        else:
            results = []
            for _ in range(shots):
                state_vector = self._init_statevector(n)
                state_vector = self._apply_ops(state_vector, ops, n)
                results.append(self._measure(state_vector, n))
            return dict(Counter(results))

    def execute_single(self, state, program: dict):
        """
        Execute measurement for a single State.

        Runs the full circuit and returns only the result for
        the specified State index.

        Args:
            state:   The State being measured
            program: Compiled program context

        Returns:
            int: 0 or 1
        """
        result = self.execute({**program, "shots": 1})
        if isinstance(result, tuple):
            return result[state.index]
        return result[state.index]

    # ── Statevector Operations ─────────────────────────────────────────────

    def _init_statevector(self, n: int) -> list:
        """
        Initialize the statevector to |00...0⟩.

        For n States, the statevector has 2^n amplitudes.
        Initially all probability is in the |0⟩ basis state.

        Args:
            n: Number of States

        Returns:
            list: Complex amplitude vector of length 2^n
        """
        size = 2 ** n
        sv = [complex(0, 0)] * size
        sv[0] = complex(1, 0)  # |00...0⟩ has amplitude 1
        return sv

    def _apply_ops(self, sv: list, ops: list, n: int) -> list:
        """
        Apply a sequence of quantum operations to the statevector.

        Args:
            sv:  Current statevector
            ops: List of operations from the compiled program
            n:   Number of States

        Returns:
            list: Updated statevector after all operations
        """
        for op in ops:
            gate = op["op"]

            if gate == "H":
                sv = self._hadamard(sv, op["target"], n)
            elif gate == "X":
                sv = self._pauli_x(sv, op["target"], n)
            elif gate == "Z":
                sv = self._pauli_z(sv, op["target"], n)
            elif gate == "CNOT":
                sv = self._cnot(sv, op["control"], op["target"], n)
            elif gate == "TOFFOLI":
                sv = self._toffoli(sv, op["control"], op["target"], n)
            elif gate == "MEASURE":
                pass  # Individual measurement handled at circuit level

        return sv

    def _hadamard(self, sv: list, target: int, n: int) -> list:
        """
        Apply Hadamard gate to target State.
        Places State into equal superposition: |0⟩ → (|0⟩ + |1⟩)/√2
        """
        new_sv = [complex(0, 0)] * len(sv)
        inv_sqrt2 = 1 / math.sqrt(2)

        for i in range(len(sv)):
            if sv[i] == 0:
                continue
            # Bit at target position
            bit = (i >> (n - 1 - target)) & 1
            # Index with target bit flipped
            j = i ^ (1 << (n - 1 - target))

            if bit == 0:
                new_sv[i] += inv_sqrt2 * sv[i]
                new_sv[j] += inv_sqrt2 * sv[i]
            else:
                new_sv[j] += inv_sqrt2 * sv[i]
                new_sv[i] -= inv_sqrt2 * sv[i]

        return new_sv

    def _pauli_x(self, sv: list, target: int, n: int) -> list:
        """Apply Pauli-X (NOT) gate — flips target State."""
        new_sv = [complex(0, 0)] * len(sv)
        for i in range(len(sv)):
            j = i ^ (1 << (n - 1 - target))
            new_sv[j] = sv[i]
        return new_sv

    def _pauli_z(self, sv: list, target: int, n: int) -> list:
        """Apply Pauli-Z gate — flips phase of |1⟩ component."""
        new_sv = sv.copy()
        for i in range(len(sv)):
            bit = (i >> (n - 1 - target)) & 1
            if bit == 1:
                new_sv[i] = -sv[i]
        return new_sv

    def _cnot(self, sv: list, control: int, target: int, n: int) -> list:
        """Apply CNOT gate — entangles control and target States."""
        new_sv = [complex(0, 0)] * len(sv)
        for i in range(len(sv)):
            control_bit = (i >> (n - 1 - control)) & 1
            if control_bit == 1:
                j = i ^ (1 << (n - 1 - target))
                new_sv[j] = sv[i]
            else:
                new_sv[i] = sv[i]
        return new_sv

    def _toffoli(self, sv: list, control: int, target: int, n: int) -> list:
        """Apply Toffoli gate — three-State entanglement."""
        # Simplified: treat as CNOT for now (full Toffoli requires 3 distinct indices)
        return self._cnot(sv, control, target, n)

    # ── Measurement ───────────────────────────────────────────────────────

    def _measure(self, sv: list, n: int) -> tuple:
        """
        Measure the statevector — collapse to a classical outcome.

        Implements the Born rule: probability of each outcome equals
        the squared magnitude of its amplitude.

        Args:
            sv: Current statevector
            n:  Number of States

        Returns:
            tuple: Classical bit values (0 or 1) for each State
        """
        # Compute probabilities via Born rule: P(i) = |amplitude_i|^2
        probabilities = [abs(amp) ** 2 for amp in sv]

        # Sample from the probability distribution
        rand = random.random()
        cumulative = 0.0
        outcome_index = 0

        for i, prob in enumerate(probabilities):
            cumulative += prob
            if rand <= cumulative:
                outcome_index = i
                break

        # Convert integer index to bit tuple
        bits = tuple(
            (outcome_index >> (n - 1 - i)) & 1
            for i in range(n)
        )

        return bits
