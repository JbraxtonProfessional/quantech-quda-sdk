"""
QUDA IonQ Backend

Translates compiled QUDA programs into Cirq circuits and
executes them on IonQ's trapped-ion simulator or real hardware.

Two execution modes:
    1. IonQ Simulator (local) — Local Cirq-based simulation via cirq_ionq
                                No credentials required. Available immediately.
                                Uses IonQNativeSampler when available, otherwise
                                falls back to cirq.Simulator().

    2. IonQ QPU (cloud) — Real trapped-ion hardware via IonQ REST API
                          Requires QUDA_IONQ_API_KEY environment variable.
                          Register at: https://ionq.com

Usage:
    # Local IonQ noise simulator (default, no key needed)
    @quda.target(hardware='ionq')
    def my_program():
        ...

    # Real IonQ quantum hardware
    # Set QUDA_IONQ_API_KEY environment variable
    @quda.target(hardware='ionq')
    def my_program():
        ...

Note on IonQ native gates:
    IonQ trapped-ion hardware natively supports GPI, GPI2, MS, and ZZ gates —
    a different gate set than superconducting backends (IBM/Google). This backend
    translates QUDA operations into the abstract QIS gateset (H, X, Z, CNOT).
    Full native gate optimization is a future enhancement.
"""

import os
import time

import requests

_IONQ_API_URL = "https://api.ionq.co/v0.3"
_TERMINAL_STATES = ("completed", "failed", "canceled", "deleted")
_POLL_INTERVAL_SECONDS = 1
_POLL_TIMEOUT_SECONDS = 3600


class IonQBackend:
    """
    IonQ trapped-ion backend for QUDA.

    Translates the QUDA operation log into a cirq.Circuit,
    then executes via the local IonQ simulator or IonQ cloud QPU.
    """

    def __init__(self, api_key: str = None, target: str = None):
        """
        Initialize the IonQ backend.

        Args:
            api_key: IonQ API key (optional — uses env var QUDA_IONQ_API_KEY)
            target:  IonQ target device e.g. 'qpu' or 'simulator' (optional)
        """
        self._api_key = api_key or os.environ.get("QUDA_IONQ_API_KEY")
        self._target = target or os.environ.get("QUDA_IONQ_TARGET", "qpu")

    # ── Public Interface ───────────────────────────────────────────────────

    def execute(self, program: dict):
        """
        Execute a compiled QUDA program on IonQ hardware.

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

        IonQ uses Cirq as its SDK layer. Maps QUDA operations to Cirq gates:
            H        → cirq.H(qubit)
            X        → cirq.X(qubit)
            Z        → cirq.Z(qubit)
            CNOT     → cirq.CNOT(control, target)
            TOFFOLI  → cirq.CNOT(control, target)  # simplified
            MEASURE  → cirq.measure(qubit, key=str(index))

        Note: IonQ hardware natively uses GPI/GPI2/MS/ZZ gates. This translation
        uses the abstract QIS gateset — native gate optimization is a future
        enhancement.

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

        Routes to IonQ cloud QPU if an API key is configured,
        otherwise falls back to the local IonQ simulator.

        Args:
            cirq_circuit: Translated cirq.Circuit
            program:      Original QUDA program (for metadata)

        Returns:
            tuple or dict: Measurement results in QUDA format
        """
        shots = program.get("shots", 1)
        n = program["state_count"]

        if self._api_key:
            return self._run_cloud(program, n, shots)
        else:
            return self._run_simulator(cirq_circuit, n, shots)

    def _run_simulator(self, cirq_circuit, n: int, shots: int):
        """
        Execute on the local IonQ noise simulator.

        Attempts to use cirq_ionq.IonQNativeSampler for trapped-ion noise
        characteristics. Falls back to cirq.Simulator() if unavailable.
        No API key or internet connection required.

        Args:
            cirq_circuit: cirq.Circuit
            n:            Number of qubits/States
            shots:        Number of executions

        Returns:
            tuple or dict: Results in QUDA format
        """
        try:
            from cirq_ionq import IonQNativeSampler
            sampler = IonQNativeSampler()
            result = sampler.run(cirq_circuit, repetitions=shots)
            return self._format_results(result, n, shots)
        except ImportError:
            pass

        import cirq

        simulator = cirq.Simulator()
        result = simulator.run(cirq_circuit, repetitions=shots)
        return self._format_results(result, n, shots)

    def _run_cloud(self, program: dict, n: int, shots: int):
        """
        Execute on real IonQ trapped-ion hardware via REST API.

        Requires QUDA_IONQ_API_KEY environment variable.
        Register at: https://ionq.com

        Args:
            program: Original QUDA program
            n:       Number of qubits/States
            shots:   Number of executions

        Returns:
            tuple or dict: Results in QUDA format
        """
        print(f"  [QUDA IonQ] Executing on: {self._target}")
        print(f"  [QUDA IonQ] Submitting job...")

        job_id = self._submit_job(program, shots)
        print(f"  [QUDA IonQ] Job ID: {job_id}")
        print(f"  [QUDA IonQ] Waiting for results...")

        self._poll_job(job_id)
        histogram = self._fetch_results(job_id)

        print(f"  [QUDA IonQ] Job complete.")

        return self._format_results(histogram, n, shots)

    # ── IonQ REST API ─────────────────────────────────────────────────────

    def _headers(self) -> dict:
        """Build IonQ API request headers."""
        return {
            "Authorization": f"apiKey {self._api_key}",
            "Content-Type": "application/json",
        }

    def _to_ionq_input(self, program: dict) -> dict:
        """
        Convert a QUDA program into IonQ's ionq.circuit.v0 JSON format.

        Uses the abstract QIS gateset. IonQ native gates (gpi, gpi2, ms, zz)
        are not used here — native gate optimization is a future enhancement.

        Args:
            program: Compiled QUDA program

        Returns:
            dict: IonQ circuit input specification
        """
        n = program["state_count"]
        ionq_circuit = []

        for op in program["operations"]:
            gate = op["op"]

            if gate == "H":
                ionq_circuit.append({"gate": "h", "target": op["target"]})

            elif gate == "X":
                ionq_circuit.append({"gate": "x", "target": op["target"]})

            elif gate == "Z":
                ionq_circuit.append({"gate": "z", "target": op["target"]})

            elif gate == "CNOT":
                ionq_circuit.append({
                    "gate": "cnot",
                    "control": op["control"],
                    "target": op["target"],
                })

            elif gate == "TOFFOLI":
                ionq_circuit.append({
                    "gate": "cnot",
                    "control": op["control"],
                    "target": op["target"],
                })

            elif gate == "MEASURE":
                pass  # Measurement handled implicitly by IonQ at circuit end

        return {
            "format": "ionq.circuit.v0",
            "gateset": "qis",
            "qubits": n,
            "circuit": ionq_circuit,
        }

    def _submit_job(self, program: dict, shots: int) -> str:
        """
        Submit a job to the IonQ REST API.

        Args:
            program: Compiled QUDA program
            shots:   Number of shots

        Returns:
            str: Job UUID

        Raises:
            RuntimeError: If job submission fails
        """
        payload = {
            "target": self._target,
            "shots": shots,
            "name": program.get("name", "quda_circuit"),
            "input": self._to_ionq_input(program),
        }

        response = requests.post(
            f"{_IONQ_API_URL}/jobs",
            json=payload,
            headers=self._headers(),
            timeout=60,
        )

        if not response.ok:
            raise RuntimeError(
                f"IonQ job submission failed ({response.status_code}): {response.text}"
            )

        job = response.json()
        return job["id"]

    def _poll_job(self, job_id: str):
        """
        Poll the IonQ API until the job reaches a terminal state.

        Args:
            job_id: Job UUID

        Raises:
            RuntimeError: If the job fails or is canceled
            TimeoutError: If polling exceeds the timeout
        """
        elapsed = 0

        while elapsed < _POLL_TIMEOUT_SECONDS:
            response = requests.get(
                f"{_IONQ_API_URL}/jobs/{job_id}",
                headers=self._headers(),
                timeout=60,
            )

            if not response.ok:
                raise RuntimeError(
                    f"IonQ job status check failed ({response.status_code}): {response.text}"
                )

            job = response.json()
            status = job.get("status", "")

            if status == "completed":
                return

            if status in ("failed", "canceled", "deleted"):
                error = job.get("failure", {}).get("error", status)
                raise RuntimeError(f"IonQ job {status}: {error}")

            if status in _TERMINAL_STATES:
                raise RuntimeError(f"IonQ job ended with status: {status}")

            time.sleep(_POLL_INTERVAL_SECONDS)
            elapsed += _POLL_INTERVAL_SECONDS

        raise TimeoutError(
            f"IonQ job {job_id} timed out after {_POLL_TIMEOUT_SECONDS} seconds."
        )

    def _fetch_results(self, job_id: str) -> dict:
        """
        Fetch measurement results from a completed IonQ job.

        Args:
            job_id: Job UUID

        Returns:
            dict: Histogram mapping bitstring outcomes to counts/probabilities
        """
        response = requests.get(
            f"{_IONQ_API_URL}/jobs/{job_id}/results",
            headers=self._headers(),
            timeout=60,
        )

        if not response.ok:
            raise RuntimeError(
                f"IonQ results fetch failed ({response.status_code}): {response.text}"
            )

        return response.json()

    # ── Result Formatting ─────────────────────────────────────────────────

    def _little_endian_to_big(self, value: int, n: int) -> int:
        """Convert IonQ's little-endian bitstring integer to big-endian."""
        bits = [(value >> i) & 1 for i in range(n)]
        return sum(bit << (n - 1 - i) for i, bit in enumerate(bits))

    def _format_results(self, ionq_result, n: int, shots: int):
        """
        Convert IonQ or Cirq results into QUDA result format.

        Accepts either:
            - A Cirq Result object (from local simulator)
            - An IonQ API histogram dict (from cloud execution)

        IonQ returns little-endian bitstrings; QUDA uses State-ordered tuples
        with State 0 as the leftmost element.

        For single-shot executions, returns a plain tuple.

        Args:
            ionq_result: Cirq result object or IonQ histogram dict
            n:           Number of qubits/States
            shots:       Number of shots executed

        Returns:
            tuple: Single result e.g. (0, 1)
            dict:  Distribution e.g. {(0,0): 512, (1,1): 512}
        """
        quda_counts = {}

        if hasattr(ionq_result, "measurements"):
            measurements = ionq_result.measurements

            if "result" in measurements:
                for row in measurements["result"]:
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

        else:
            histogram = ionq_result
            inner = next(iter(histogram.values()))
            if isinstance(inner, dict):
                histogram = inner

            for bitstring, value in histogram.items():
                little_endian = int(bitstring)
                big_endian = self._little_endian_to_big(little_endian, n)
                bits = tuple((big_endian >> (n - 1 - i)) & 1 for i in range(n))

                if isinstance(value, float) and value <= 1.0:
                    count = round(value * shots)
                else:
                    count = int(value)

                quda_counts[bits] = quda_counts.get(bits, 0) + count

        if shots == 1:
            return max(quda_counts, key=quda_counts.get)

        return quda_counts
