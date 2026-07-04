import os
import time
from typing import Callable, Iterable, Optional, Tuple, TypeVar

T = TypeVar("T")


NETWORK_ERROR_NAMES = (
    "ConnectionError",
    "ConnectionResetError",
    "ConnectTimeout",
    "ReadTimeout",
    "Timeout",
    "SSLError",
    "ChunkedEncodingError",
)


def is_network_error(exc: BaseException) -> bool:
    current: Optional[BaseException] = exc

    while current is not None:
        name = current.__class__.__name__
        if name in NETWORK_ERROR_NAMES:
            return True

        text = str(current).lower()
        if any(
            marker in text
            for marker in (
                "connection reset",
                "connection aborted",
                "timed out",
                "timeout",
                "temporarily unavailable",
                "failed to establish a new connection",
                "max retries exceeded",
                "forzosamente",
                "interrupcion de una conexion",
                "interrupción de una conexión",
            )
        ):
            return True

        current = current.__cause__ or current.__context__

    return False


def _log(logger, level: str, message: str) -> None:
    if logger is not None:
        getattr(logger, level.lower(), logger.info)(message)
    else:
        print(message, flush=True)


def pause_until_resume(reason: str, logger=None, poll_seconds: int = 5) -> None:
    resume_file = os.getenv("PYFLOW_RESUME_FILE")
    control_dir = os.getenv("PYFLOW_CONTROL_DIR")

    if not resume_file and control_dir:
        resume_file = os.path.join(control_dir, "resume.flag")

    if not resume_file:
        _log(logger, "warning", f"No hay canal de pausa configurado. Motivo: {reason}")
        return

    os.makedirs(os.path.dirname(resume_file), exist_ok=True)

    if os.path.exists(resume_file):
        try:
            os.remove(resume_file)
        except OSError:
            pass

    print(f"PYFLOW_PAUSED={reason}", flush=True)
    _log(logger, "warning", f"Ejecucion pausada. Motivo: {reason}")

    while not os.path.exists(resume_file):
        time.sleep(max(1, int(poll_seconds)))

    try:
        os.remove(resume_file)
    except OSError:
        pass

    print("PYFLOW_RESUMED=Continuando ejecucion despues de pausa manual.", flush=True)
    _log(logger, "info", "Ejecucion reanudada por el usuario.")


def run_with_network_pause(
    action: Callable[[], T],
    description: str,
    logger=None,
    recoverable_errors: Iterable[type[BaseException]] = (Exception,),
    poll_seconds: int = 5,
) -> T:
    while True:
        try:
            return action()
        except tuple(recoverable_errors) as exc:
            if not is_network_error(exc):
                raise

            pause_until_resume(
                f"Error de red durante {description}: {exc}",
                logger=logger,
                poll_seconds=poll_seconds,
            )
