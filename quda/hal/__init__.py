"""
QUDA Hardware Abstraction Layer (HAL)

The HAL routes compiled QUDA programs to the appropriate backend.
"""

from .simulator import SimulatorBackend

_BACKENDS = {
    "simulator": SimulatorBackend,
}

try:
    from .ibm import IBMBackend
    _BACKENDS["ibm"] = IBMBackend
except ImportError:
    pass

try:
    from .google import GoogleBackend
    _BACKENDS["google"] = GoogleBackend
except ImportError:
    pass

try:
    from .ionq import IonQBackend
    _BACKENDS["ionq"] = IonQBackend
except ImportError:
    pass


def route(backend_name: str, program: dict):
    backend = _resolve(backend_name)
    return backend.execute(program)


def route_single(backend_name: str, state, program: dict):
    backend = _resolve(backend_name)
    return backend.execute_single(state, program)


def _resolve(backend_name: str):
    name = backend_name.lower().strip()
    if name not in _BACKENDS:
        available = ", ".join(_BACKENDS.keys())
        raise QUDAHALError(
            f"Backend '{backend_name}' is not available. "
            f"Available backends: {available}."
        )
    return _BACKENDS[name]()


def available_backends() -> list:
    return list(_BACKENDS.keys())


class QUDAHALError(Exception):
    pass
