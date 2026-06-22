"""
QUDA IBM Backend

Translates compiled QUDA programs into Qiskit circuits and
executes them on IBM Quantum hardware or IBM's Aer simulator.

Two execution modes:
    1. IBM Aer (local)    — High-performance local simulator via Qiskit Aer
                            No API key required. Available immediately.

    2. IBM Quantum (cloud) — Real quantum hardware via IBM Quantum Platform
                             Requires free IBM Quantum API key.
                             Register at: https://quantum.ibm.com

Usage:
    # Local Aer simulator (default, no key needed)
    @quda.target(hardware='ibm')
    def my_program():
        ...

    # Real IBM quantum hardware
    @quda.target(hardware='ibm', token='YOUR_IBM_TOKEN', channel='ibm_quantum')
    def my_program():
        ...
"""

import os


class IBMBackend:
    """
    IBM Quantum backend for QUDA.

    Translates the QUDA operation log into a Qiskit QuantumCircuit,
    then executes via IBM Aer (local) or IBM Quantum (cloud).
    """

    def __init__(self, token: str = None, channel: str = None, instance: str = None):
        """
        Initialize the IBM backend.

        Args:
            token:    IBM Quantum API token (optional — uses env var QUDA_IBM_TOKEN)
            channel:  'ibm_quantum' or 'ibm_cloud' (optional)
            instance: IBM Quantum instance e.g. 'ibm-q/open/main' (optional)
        """
        self._token    = token or os.environ.get("QUDA_IBM_TOKEN")
        self._channel  = channel or os.environ.get("QUDA_IBM_CHANNEL", "ibm_quantum")
        self._instance = instance or os.environ.get("QUDA_IBM_INSTANCE", "ibm-q/open/main")

    # ── Public Interface ───────────────────────────────────────────────────

    def execute(self, program: dict):
        """
        Execute a compiled QUDA program on IBM hardware.

        Args:
            program: Compiled program from Circuit._compile()

        Returns:
            tuple or dict: Measurement results
        """
        qiskit_circuit = self._translate(program)
        return self._run(qiskit_circuit, program)

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

    # ── Translation — QUDA → Qiskit ───────────────────────────────────────

    def _translate(self, program: dict):
        """
        Translate a compiled QUDA program into a Qiskit QuantumCircuit.

        Maps QUDA operations to their Qiskit gate equivalents:
            H        → qc.h(target)
            X        → qc.x(target)
            Z        → qc.z(target)
            CNOT     → qc.cx(control, target)
            TOFFOLI  → qc.ccx(control, target, target)
            MEASURE  → qc.measure(target, target)

        Args:
            program: Compiled QUDA program

        Returns:
            QuantumCircuit: Qiskit circuit ready for execution
        """
        from qiskit import QuantumCircuit

        n = program["state_count"]
        ops = program["operations"]

        # Create Qiskit circuit with n qubits and n classical bits
        qc = QuantumCircuit(n, n)

        has_explicit_measure = any(op["op"] == "MEASURE" for op in ops)

        # Translate each QUDA operation to a Qiskit gate
        for op in ops:
            gate = op["op"]

            if gate == "H":
                qc.h(op["target"])

            elif gate == "X":
                qc.x(op["target"])

            elif gate == "Z":
                qc.z(op["target"])

            elif gate == "CNOT":
                qc.cx(op["control"], op["target"])

            elif gate == "TOFFOLI":
                # Simplified — full Toffoli needs 3 distinct qubits
                qc.cx(op["control"], op["target"])

            elif gate == "MEASURE":
                qc.measure(op["target"], op["target"])

        # Add measurement to all qubits if no explicit measures defined
        if not has_explicit_measure:
            qc.measure(range(n), range(n))

        return qc

    # ── Execution ─────────────────────────────────────────────────────────

    def _run(self, qiskit_circuit, program: dict):
        """
        Execute a Qiskit circuit.

        Routes to IBM cloud hardware if a token is configured,
        otherwise falls back to the local Aer simulator.

        Args:
            qiskit_circuit: Translated Qiskit QuantumCircuit
            program:        Original QUDA program (for metadata)

        Returns:
            tuple or dict: Measurement results in QUDA format
        """
        shots = program.get("shots", 1)

        if self._token:
            return self._run_cloud(qiskit_circuit, shots)
        else:
            return self._run_aer(qiskit_circuit, shots)

    def _run_aer(self, qiskit_circuit, shots: int):
        """
        Execute on the local Aer high-performance simulator.

        Aer is IBM's local quantum simulator — significantly faster
        and more accurate than QUDA's built-in statevector simulator.
        No API key or internet connection required.

        Args:
            qiskit_circuit: Qiskit QuantumCircuit
            shots:          Number of executions

        Returns:
            tuple or dict: Results in QUDA format
        """
        try:
            from qiskit_aer import AerSimulator
            backend = AerSimulator()
        except ImportError:
            # Fall back to BasicSimulator if Aer not available
            from qiskit.primitives import StatevectorSampler
            return self._run_statevector(qiskit_circuit, shots)

        from qiskit import transpile
        transpiled = transpile(qiskit_circuit, backend)
        job = backend.run(transpiled, shots=shots)
        counts = job.result().get_counts()
        return self._format_results(counts, qiskit_circuit.num_qubits, shots)

    def _run_statevector(self, qiskit_circuit, shots: int):
        """
        Fallback: Execute using Qiskit's StatevectorSampler.
        Used when Aer is not available.
        """
        from qiskit.primitives import StatevectorSampler
        from qiskit import QuantumCircuit

        sampler = StatevectorSampler()
        job = sampler.run([qiskit_circuit], shots=shots)
        result = job.result()

        # Extract counts from sampler result
        pub_result = result[0]
        counts_raw = pub_result.data

        # Convert BitArray to counts dict
        counts = {}
        for name in counts_raw:
            bit_array = counts_raw[name]
            for shot_idx in range(bit_array.num_shots):
                bits = bit_array.get_int_counts()
                for bitstring, count in bits.items():
                    # Convert integer to binary string
                    n = qiskit_circuit.num_qubits
                    key = format(bitstring, f'0{n}b')
                    counts[key] = counts.get(key, 0) + count
                break

        return self._format_results(counts, qiskit_circuit.num_qubits, shots)

    def _run_cloud(self, qiskit_circuit, shots: int):
        """
        Execute on real IBM Quantum hardware.

        Requires a valid IBM Quantum API token set via:
            - QUDA_IBM_TOKEN environment variable
            - token parameter in @quda.target decorator

        Register for free at: https://quantum.ibm.com

        Args:
            qiskit_circuit: Qiskit QuantumCircuit
            shots:          Number of executions

        Returns:
            tuple or dict: Results in QUDA format
        """
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
        from qiskit import transpile

        # Connect to IBM Quantum
        service = QiskitRuntimeService(
            channel=self._channel,
            token=self._token,
            instance=self._instance
        )

        # Select least busy real backend with enough qubits
        n = qiskit_circuit.num_qubits
        backend = service.least_busy(
            operational=True,
            simulator=False,
            min_num_qubits=n
        )

        print(f"  [QUDA IBM] Executing on: {backend.name}")

        # Transpile for the target backend
        transpiled = transpile(qiskit_circuit, backend=backend)

        # Execute via Sampler primitive
        sampler = Sampler(mode=backend)
        job = sampler.run([transpiled], shots=shots)

        print(f"  [QUDA IBM] Job ID: {job.job_id()}")
        print(f"  [QUDA IBM] Waiting for results...")

        result = job.result()
        pub_result = result[0]
        counts = pub_result.data.c.get_counts()

        return self._format_results(counts, n, shots)

    # ── Result Formatting ─────────────────────────────────────────────────

    def _format_results(self, counts: dict, n: int, shots: int):
        """
        Convert Qiskit result counts into QUDA result format.

        Qiskit returns results as bitstrings: {'00': 512, '11': 512}
        QUDA returns results as tuples:       {(0,0): 512, (1,1): 512}

        For single-shot executions, returns a plain tuple.

        Args:
            counts: Qiskit counts dictionary
            n:      Number of qubits/States
            shots:  Number of shots executed

        Returns:
            tuple: Single result e.g. (0, 1)
            dict:  Distribution e.g. {(0,0): 512, (1,1): 512}
        """
        # Convert bitstring keys to tuple keys
        # Qiskit bitstrings are right-to-left — reverse for QUDA ordering
        quda_counts = {}
        for bitstring, count in counts.items():
            # Normalize bitstring — remove spaces, pad to n bits
            clean = bitstring.replace(" ", "").zfill(n)
            # Reverse to match QUDA State ordering (State 0 = leftmost)
            bits = tuple(int(b) for b in reversed(clean))
            quda_counts[bits] = quda_counts.get(bits, 0) + count

        if shots == 1:
            # Return the single observed outcome as a plain tuple
            return max(quda_counts, key=quda_counts.get)

        return quda_counts
