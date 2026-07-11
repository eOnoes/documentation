"""
Audit Orchestrator — Entry Point

Creates the AuditOrchestrator and runs the main loop.
Handles graceful shutdown on SIGTERM/SIGINT.
"""

import sys
import signal
import logging

from .orchestrator import AuditOrchestrator

logger = logging.getLogger("orchestrator")


def setup_logging():
    """Configure logging for the orchestrator."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


def main():
    """Entry point: create orchestrator, set up signals, run loop."""
    setup_logging()
    logger.info("Audit Orchestrator starting up")

    orchestrator = AuditOrchestrator()
    orchestrator.load_projects()

    # Graceful shutdown on SIGTERM/SIGINT
    shutdown_requested = False

    def _handle_signal(signum, frame):
        nonlocal shutdown_requested
        sig_name = signal.Signals(signum).name
        logger.info("Received %s — shutting down gracefully", sig_name)
        shutdown_requested = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Install the shutdown check as a custom exception or use a flag
    # We override run() with a signal-aware version
    import time
    from .config import MARKER_CHECK_INTERVAL

    iteration = 0
    logger.info("Starting orchestrator loop (interval=%ds)", MARKER_CHECK_INTERVAL)

    while not shutdown_requested:
        try:
            orchestrator.run_once()
        except Exception as e:
            logger.error("Unhandled exception in run_once: %s", e)

        iteration += 1

        # Sleep in small increments so signals are processed
        for _ in range(MARKER_CHECK_INTERVAL):
            if shutdown_requested:
                break
            time.sleep(1)

    logger.info("Orchestrator stopped after %d iterations", iteration)


if __name__ == "__main__":
    main()
