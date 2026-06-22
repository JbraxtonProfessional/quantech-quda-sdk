"""
QUDA Google Cirq Backend

Translates compiled QUDA programs into Cirq circuits and
executes them on Google's local simulator or Quantum AI hardware.

Two execution modes:
    1. Cirq Simulator (local) — High-performance local simulator via Cirq
                                No credentials required. Available immediately.

    2. Google Quantum AI (cloud) — Real quantum hardware via Google Quantum AI
                                   Requires QUDA_GOOGLE_PROJECT_ID and
                                   QUDA_GOOGLE_PROCESSOR_ID environment variables.
                                   Register at: https://quantumai.google

Usage:
    # Local Cirq simulator (default, no credentials needed)
    @quda.target(hardware='google')
    def my_program():
        ...

    # Real Google quantum hardware
    # Set QUDA_GOOGLE_PROJECT_ID and QUDA_GOOGLE_PROCESSOR_ID env vars
    @quda.target(hardware='google')
    def my_program():
        ...
"""

import os


class GoogleBackend:
    """
    Google Cirq backend for QUDA.

    Translates the QUDA operation log into a cirq.Circuit,
    then executes via the local Cirq simulator or Google Quantum AI.
    """

    def __init__(self, project_id: str = None, processor_id: str = None):
        """
        Initialize the Google backend.

        Args:
            project_id:    Google Cloud project ID (optional — uses QUDA_GOOGLE_PROJECT_ID)
            processor_id:  Quantum processor ID (optional — uses QUDA_GOOGLE_PROCESSOR_ID)
        """
        self._project_id   = project_id or os.environ.get("QUDA_GOOGLE_PROJECT_ID")
        self._processor_id = processor_id or os.environ.get("QUDA_GOOGLE_PROCESSOR_ID")

    # ── Public Interface ───────────────────────────────────────────────────

    def execute(self, program: dict):
        """
        Execute a compiled QUDA program on Google hardware.

        Args:
            program: Compiled program from Circuit._compile()

        Returns:
            tuple or dict: Measurement results
        """
        cirq_circuit = self._translate(program)
        return self._run(cirq_circuit, program)

    def execute_single(self, state, program: dict):
        """
        Execute measurement for a single State.

        Args:
            state:   The State being measured
            program: Compiled program context

        Returns:
            int: 0 or 1
        """
        result = self.execute({**program, "shots": 1})
        if isinstance(result, tuple):
            return result[state.index]
        return list(result.keys())[0][state.index]

    # ── Translation — QUDA → Cirq ─────────────────────────────────────────

    def _translate(self, program: dict):
        """
        Translate a compiled QUDA program into a cirq.Circuit.

        Maps QUDA operations to their Cirq gate equivalents:
            H        → cirq.H(qubit)
            X        → cirq.X(qubit)
            Z        → cirq.Z(qubit)
            CNOT     → cirq.CNOT(control, target)
            TOFFOLI  → cirq.CNOT(control, target)  # simplified
            MEASURE  → cirq.measure(qubit, key=str(index))

        Args:
            program: Compiled QUDA program

        Returns:
            cirq.Circuit: Cirq circuit ready for execution
        """
        import cirq

        n = program["state_count"]
        ops = program["operations"]
        qubits = cirq.LineQubit.range(n)

        moments = []
        has_explicit_measure = any(op["op"] == "MEASURE" for op in ops)

        for op in ops:
            gate = op["op"]

            if gate == "H":
                moments.append(cirq.H(qubits[op["target"]]))

            elif gate == "X":
                moments.append(cirq.X(qubits[op["target"]]))

            elif gate == "Z":
                moments.append(cirq.Z(qubits[op["target"]]))

            elif gate == "CNOT":
                moments.append(cirq.CNOT(qubits[op["control"]], qubits[op["target"]]))

            elif gate == "TOFFOLI":
                # Simplified — full Toffoli needs 3 distinct qubits
                moments.append(cirq.CNOT(qubits[op["control"]], qubits[op["target"]]))

            elif gate == "MEASURE":
                moments.append(cirq.measure(qubits[op["target"]], key=str(op["target"])))

        if not has_explicit_measure:
            moments.append(cirq.measure(*qubits, key="result"))

        return cirq.Circuit(moments)

    # ── Execution ─────────────────────────────────────────────────────────

    def _run(self, cirq_circuit, program: dict):
        """
        Execute a Cirq circuit.

        Routes to Google Quantum AI cloud hardware if project and processor
        IDs are configured, otherwise falls back to the local Cirq simulator.

        Args:
            cirq_circuit: Translated cirq.Circuit
            program:      Original QUDA program (for metadata)

        Returns:
            tuple or dict: Measurement results in QUDA format
        """
        shots = program.get("shots", 1)
        n = program["state_count"]

        if self._project_id and self._processor_id:
            return self._run_cloud(cirq_circuit, n, shots)
        else:
            return self._run_simulator(cirq_circuit, n, shots)

    def _run_simulator(self, cirq_circuit, n: int, shots: int):
        """
        Execute on the local Cirq simulator.

        Cirq's built-in simulator faithfully simulates quantum circuits
        locally. No credentials or internet connection required.

        Args:
            cirq_circuit: cirq.Circuit
            n:            Number of qubits/States
            shots:        Number of executions

        Returns:
            tuple or dict: Results in QUDA format
        """
        import cirq

        simulator = cirq.Simulator()
        result = simulator.run(cirq_circuit, repetitions=shots)
        return self._format_results(result, n, shots)

    def _run_cloud(self, cirq_circuit, n: int, shots: int):
        """
        Execute on real Google Quantum AI hardware.

        Requires QUDA_GOOGLE_PROJECT_ID and QUDA_GOOGLE_PROCESSOR_ID
        environment variables to be set.

        Register at: https://quantumai.google

        Args:
            cirq_circuit: cirq.Circuit
            n:            Number of qubits/States
            shots:        Number of executions

        Returns:
            tuple or dict: Results in QUDA format
        """
        from cirq_google import Sampler

        print(f"  [QUDA Google] Executing on: {self._processor_id}")
        print(f"  [QUDA Google] Project: {self._project_id}")

        sampler = Sampler(
            processor_id=self._processor_id,
            project_id=self._project_id,
        )
        result = sampler.run(cirq_circuit, repetitions=shots)

        print(f"  [QUDA Google] Job complete.")

        return self._format_results(result, n, shots)

    # ── Result Formatting ─────────────────────────────────────────────────

    def _format_results(self, cirq_result, n: int, shots: int):
        """
        Convert Cirq measurement results into QUDA result format.

        Cirq returns results as measurement key → ndarray of bit values.
        QUDA returns results as tuples: (0, 0) or {(0,0): 512, (1,1): 512}

        For single-shot executions, returns a plain tuple.

        Args:
            cirq_result: Cirq simulation/sampling result object
            n:           Number of qubits/States
            shots:       Number of shots executed

        Returns:
            tuple: Single result e.g. (0, 1)
            dict:  Distribution e.g. {(0,0): 512, (1,1): 512}
        """
        measurements = cirq_result.measurements
        quda_counts = {}

        if "result" in measurements:
            rows = measurements["result"]
            for row in rows:
                bits = tuple(int(b) for b in row)
                quda_counts[bits] = quda_counts.get(bits, 0) + 1
        else:
            for shot_idx in range(shots):
                bits = tuple(
                    int(measurements[str(i)][shot_idx][0])
                    for i in range(n)
                    if str(i) in measurements
                )
                if len(bits) == n:
                    quda_counts[bits] = quda_counts.get(bits, 0) + 1

        if shots == 1:
            return max(quda_counts, key=quda_counts.get)

        return quda_counts
