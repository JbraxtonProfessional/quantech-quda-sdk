"""
QUDA Circuit — The Quantum Program

A Circuit is the execution context for all quantum operations in QUDA.
States and Fields only exist inside a Circuit. Operations only execute
inside a Circuit. Measurement only happens through a Circuit.

Analogous to a Kernel in CUDA — the function that runs on the hardware,
containing all threads and defining all work to be done.
"""

from .state import State, QUDAStateError
from .field import Field


class Circuit:
    """
    The quantum program — the execution context for all QUDA operations.

    A Circuit owns all States and Fields created within it. It compiles
    the operation log into hardware instructions and dispatches to the
    configured backend via the Hardware Abstraction Layer (HAL).

    Example:
        import quda

        @quda.target(hardware='ibm')
        def bell_state():
            circuit = quda.Circuit()
            field = circuit.field(size=2)

            field[0].superpose()
            field[0].entangle(field[1])

            return circuit.measure()

        result = bell_state()
        # Returns (0, 0) or (1, 1) — never (0, 1) or (1, 0)
    """

    def __init__(self, name: str = None):
        """
        Create a new quantum Circuit.

        Args:
            name: Optional human-readable name for debugging and telemetry
        """
        self._name      = name or "circuit"
        self._states    = []       # All States in this Circuit
        self._fields    = []       # All Fields in this Circuit
        self._closed    = False    # True after measurement — no new operations
        self._results   = None     # Classical results after measurement
        self._backend   = None     # Set by @quda.target decorator
        self._shots     = 1        # Number of executions (for statistical results)

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def state_count(self) -> int:
        return len(self._states)

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def results(self):
        return self._results

    # ── Building the Circuit ───────────────────────────────────────────────

    def state(self, name: str = None) -> State:
        """
        Create a single State in this Circuit.

        Args:
            name: Optional human-readable name

        Returns:
            State: A new State bound to this Circuit

        Example:
            circuit = quda.Circuit()
            s = circuit.state(name='control')
            s.superpose()
        """
        self._assert_open("create a State")
        s = State(self, index=len(self._states), name=name)
        self._states.append(s)
        return s

    def field(self, size: int, name: str = None) -> Field:
        """
        Create a Field of States in this Circuit.

        A Field is the standard way to work with multiple States.
        All States in the Field are created simultaneously and
        can entangle freely with each other.

        Args:
            size: Number of States in the Field
            name: Optional human-readable name

        Returns:
            Field: A new Field bound to this Circuit

        Example:
            circuit = quda.Circuit()
            field = circuit.field(size=4)
            field.superpose_all().entangle_chain()
        """
        self._assert_open("create a Field")

        if size < 1:
            raise QUDACircuitError("A Field must contain at least 1 State.")

        f = Field(
            circuit=self,
            size=size,
            name=name or f"field{len(self._fields)}",
            index_offset=len(self._states)
        )

        # Register all States from this Field in the Circuit's State registry
        self._states.extend(f.states)
        self._fields.append(f)
        return f

    def shots(self, n: int):
        """
        Set the number of executions for statistical measurement.

        Quantum measurement is probabilistic. Running a Circuit multiple
        times (shots) builds a probability distribution over outcomes.

        Args:
            n: Number of shots (executions)

        Returns:
            self — enables method chaining

        Example:
            result = circuit.shots(1024).measure()
            # Returns distribution: {(0,0): 512, (1,1): 512}
        """
        self._assert_open("set shots")
        if n < 1:
            raise QUDACircuitError("Shots must be at least 1.")
        self._shots = n
        return self

    # ── Measurement ───────────────────────────────────────────────────────

    def measure(self):
        """
        Measure all States in this Circuit — collapse and return results.

        Measurement is the final act of a quantum Circuit. It collapses
        all States from superposition into classical values and closes
        the Circuit. No further operations can be applied after measurement.

        Returns:
            tuple: Classical values (0 or 1) for each State, in order.
                   If shots > 1, returns a dict of outcome distributions.

        Example:
            # Single shot
            result = circuit.measure()
            # (0, 1, 0, 1)

            # Multiple shots
            result = circuit.shots(1024).measure()
            # {(0, 0): 521, (1, 1): 503}

        Raises:
            QUDACircuitError: If the Circuit is already closed or has no States
        """
        if self._closed:
            raise QUDACircuitError(
                "This Circuit has already been measured. "
                "Measurement is irreversible. Create a new Circuit to run again."
            )

        if not self._states:
            raise QUDACircuitError(
                "Cannot measure an empty Circuit. "
                "Add States with circuit.state() or circuit.field() first."
            )

        # Compile the operation log into hardware instructions
        program = self._compile()

        # Dispatch to the backend via HAL
        raw_results = self._dispatch(program)

        # Close the Circuit — no further operations permitted
        self._closed = True
        self._results = raw_results

        # Mark all States as collapsed
        for state in self._states:
            if not state.is_collapsed:
                state._status = state._status.__class__.COLLAPSED

        return raw_results

    # ── Compilation ───────────────────────────────────────────────────────

    def _compile(self) -> dict:
        """
        Compile the Circuit's operation log into a hardware-agnostic program.

        The compiled program is a structured representation of all quantum
        operations, ready for translation by the HAL into backend-specific
        instructions.

        Returns:
            dict: The compiled program — {states, operations, shots, metadata}
        """
        operations = []
        for state in self._states:
            operations.extend(state.ops())

        return {
            "name": self._name,
            "state_count": len(self._states),
            "operations": operations,
            "shots": self._shots,
            "metadata": {
                "fields": len(self._fields),
                "states": len(self._states)
            }
        }

    def _dispatch(self, program: dict):
        """
        Dispatch the compiled program to the configured backend via HAL.

        If no backend is configured (no @quda.target decorator),
        dispatches to the local simulator for development.

        Args:
            program: The compiled program from _compile()

        Returns:
            Measurement results from the backend
        """
        from .decorators import get_active_backend
        from .hal import route

        backend = self._backend or get_active_backend()
        return route(backend, program)

    def _execute_single(self, state: State):
        """
        Execute measurement for a single State.
        Called by State.measure() for individual State collapse.

        Args:
            state: The State being measured

        Returns:
            int: 0 or 1
        """
        from .decorators import get_active_backend
        from .hal import route_single
        backend = self._backend or get_active_backend()
        return route_single(backend, state, self._compile())

    # ── Inspection ────────────────────────────────────────────────────────

    def diagram(self) -> str:
        """
        Return a text diagram of this Circuit's operation sequence.

        Useful for debugging and understanding circuit structure
        before dispatching to hardware.

        Returns:
            str: ASCII circuit diagram
        """
        lines = [f"QUDA Circuit: '{self._name}'",
                 f"States: {len(self._states)} | Fields: {len(self._fields)} | Shots: {self._shots}",
                 "─" * 50]

        for state in self._states:
            ops = " → ".join(op["op"] for op in state.ops()) or "no ops"
            lines.append(f"  {state.name:15} | {ops}")

        lines.append("─" * 50)
        status = "CLOSED" if self._closed else "OPEN"
        lines.append(f"Status: {status}")
        return "\n".join(lines)

    def __repr__(self):
        status = "closed" if self._closed else "open"
        return (f"<Circuit '{self._name}' "
                f"[{len(self._states)} states, {len(self._fields)} fields, {status}]>")

    # ── Internal Guards ───────────────────────────────────────────────────

    def _assert_open(self, action: str):
        if self._closed:
            raise QUDACircuitError(
                f"Cannot {action} in a closed Circuit. "
                f"A Circuit closes after measurement. Create a new Circuit."
            )


# ── Exceptions ────────────────────────────────────────────────────────────

class QUDACircuitError(Exception):
    """Raised when an invalid operation is attempted on a Circuit."""
    pass
