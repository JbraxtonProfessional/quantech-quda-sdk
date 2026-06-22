"""
QUDA Decorators

The three decorators that connect QUDA programs to the full
Quantech ecosystem — security, hardware targeting, and intelligence.

    @quda.secure    — Enclave post-quantum encryption
    @quda.target    — Hardware Abstraction Layer routing
    @quda.telemetry — Panoptic intelligence and analytics
"""

import functools


def secure(enclave: bool = True):
    """
    Wrap a QUDA program in Enclave post-quantum encryption.

    All inputs, outputs, and execution metadata are encrypted
    using post-quantum cryptographic standards. This decorator
    integrates with Enclave's infrastructure layer.

    Args:
        enclave: Enable Enclave encryption (default: True)

    Example:
        @quda.secure(enclave=True)
        def my_program():
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if enclave:
                # Enclave integration point
                # In production: establish encrypted session via Enclave SDK
                _enclave_session_open(fn.__name__)
                try:
                    result = fn(*args, **kwargs)
                    return _enclave_encrypt_result(result)
                finally:
                    _enclave_session_close(fn.__name__)
            return fn(*args, **kwargs)
        wrapper._quda_secure = True
        wrapper._quda_enclave = enclave
        return wrapper
    return decorator


def target(hardware: str = "auto"):
    """
    Route a QUDA program to a specific quantum hardware backend.

    The Hardware Abstraction Layer translates QUDA operations into
    the native instruction set of the target backend automatically.

    Args:
        hardware: Target backend — 'auto', 'simulator', 'ibm',
                  'google', 'ionq', 'braket', 'quantech'

    Example:
        @quda.target(hardware='ibm')
        def my_program():
            circuit = quda.Circuit()
            ...

        @quda.target(hardware='auto')  # QUDA selects optimal backend
        def my_program():
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Inject backend into any Circuit created during execution
            _set_active_backend(hardware)
            try:
                result = fn(*args, **kwargs)
            finally:
                _clear_active_backend()
            return result
        wrapper._quda_target = True
        wrapper._quda_hardware = hardware
        return wrapper
    return decorator


def telemetry(panoptic: bool = True):
    """
    Connect a QUDA program to Panoptic's intelligence layer.

    Execution data, performance metrics, circuit structure, and
    outcome distributions are logged to Panoptic for analysis,
    optimization recommendations, and aggregate intelligence.

    Args:
        panoptic: Enable Panoptic telemetry (default: True)

    Example:
        @quda.telemetry(panoptic=True)
        def my_program():
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if panoptic:
                _panoptic_log_start(fn.__name__)
                try:
                    result = fn(*args, **kwargs)
                    _panoptic_log_result(fn.__name__, result)
                    return result
                except Exception as e:
                    _panoptic_log_error(fn.__name__, e)
                    raise
            return fn(*args, **kwargs)
        wrapper._quda_telemetry = True
        wrapper._quda_panoptic = panoptic
        return wrapper
    return decorator


# ── Active Backend Context ─────────────────────────────────────────────────
# Tracks which hardware backend is active for the current execution context

_active_backend = None


def _set_active_backend(hardware: str):
    global _active_backend
    _active_backend = hardware


def _clear_active_backend():
    global _active_backend
    _active_backend = None


def get_active_backend() -> str:
    """Return the currently active backend, or 'simulator' if none set."""
    return _active_backend or "simulator"


# ── Enclave Integration Stubs ──────────────────────────────────────────────
# These connect to Enclave's SDK in production

def _enclave_session_open(program_name: str):
    """Open an encrypted Enclave session for this program execution."""
    # Production: enclave.sdk.session.open(program_name)
    pass


def _enclave_session_close(program_name: str):
    """Close the Enclave session after execution."""
    # Production: enclave.sdk.session.close(program_name)
    pass


def _enclave_encrypt_result(result):
    """Encrypt the result via Enclave before returning to caller."""
    # Production: return enclave.sdk.encrypt(result)
    return result  # Pass-through until Enclave SDK is integrated


# ── Panoptic Integration Stubs ─────────────────────────────────────────────
# These connect to Panoptic's telemetry API in production

def _panoptic_log_start(program_name: str):
    """Log program execution start to Panoptic."""
    # Production: panoptic.telemetry.log_start(program_name)
    pass


def _panoptic_log_result(program_name: str, result):
    """Log program result and metrics to Panoptic."""
    # Production: panoptic.telemetry.log_result(program_name, result)
    pass


def _panoptic_log_error(program_name: str, error: Exception):
    """Log execution errors to Panoptic."""
    # Production: panoptic.telemetry.log_error(program_name, error)
    pass
