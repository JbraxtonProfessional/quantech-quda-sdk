"""
QUDA — Quantum Unified Device Architecture
==========================================

Just as CUDA defined the GPU era, QUDA defines the quantum era.

QUDA is the universal quantum programming layer. Write once.
Run on any quantum hardware. Secure by Enclave. Smart by Panoptic.

Quickstart:
    import quda

    @quda.target(hardware='simulator')
    def bell_state():
        circuit = quda.Circuit()
        field = circuit.field(size=2)

        field[0].superpose()
        field[0].entangle(field[1])

        return circuit.measure()

    result = bell_state()
    print(result)  # (0, 0) or (1, 1) — never (0, 1) or (1, 0)

Core Objects:
    Circuit   — The quantum program execution context
    Field     — A collection of States within a Circuit
    State     — The fundamental unit of quantum execution

Decorators:
    @secure   — Enclave post-quantum encryption
    @target   — Hardware backend routing
    @telemetry — Panoptic intelligence integration

Version: 0.1.1
Company: Quantech
"""

from .circuit    import Circuit, QUDACircuitError
from .field      import Field, QUDAFieldError
from .state      import State, StateStatus, QUDAStateError
from .decorators import secure, target, telemetry, get_active_backend
from .hal        import available_backends, QUDAHALError

__version__ = "0.1.1"
__author__  = "Quantech"
__all__ = [
    # Core
    "Circuit",
    "Field",
    "State",
    "StateStatus",
    # Decorators
    "secure",
    "target",
    "telemetry",
    # Utilities
    "available_backends",
    "get_active_backend",
    # Exceptions
    "QUDACircuitError",
    "QUDAFieldError",
    "QUDAStateError",
    "QUDAHALError",
]


def version():
    """Return the current QUDA version string."""
    return __version__


def backends():
    """Return a list of currently available hardware backends."""
    return available_backends()
