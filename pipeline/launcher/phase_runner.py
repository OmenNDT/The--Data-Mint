"""Phase Runner - Subprocess execution helper for pipeline phases."""

import subprocess
import threading
import logging
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, List

logger = logging.getLogger(__name__)


@dataclass
class PhaseResult:
    """Result of a single phase execution."""
    phase_id: int
    phase_name: str
    success: bool
    exit_code: int
    duration_seconds: float
    output_dir: Optional[Path] = None
    error_message: Optional[str] = None


class PhaseRunner:
    """Executes pipeline phases as subprocesses with streaming output."""

    def __init__(
        self,
        python_executable: str = "python",
        pipeline_dir: Optional[Path] = None
    ):
        """Initialize PhaseRunner.

        Args:
            python_executable: Path to Python interpreter
            pipeline_dir: Path to pipeline root directory
        """
        self.python_executable = python_executable
        self.pipeline_dir = pipeline_dir or Path(__file__).parent.parent
        self._current_process: Optional[subprocess.Popen] = None
        self._cancel_requested = False

    def run(
        self,
        phase_id: int,
        phase_name: str,
        script_path: Path,
        args: List[str],
        progress_callback: Optional[Callable[[str], None]] = None,
        python_override: Optional[str] = None,
    ) -> PhaseResult:
        """Run a single pipeline phase.

        Args:
            phase_id: Phase number (1-9)
            phase_name: Human-readable phase name
            script_path: Path to the Python script to execute
            args: Command-line arguments for the script
            progress_callback: Optional callback to receive stdout lines

        Returns:
            PhaseResult with execution details
        """
        import time
        start_time = time.time()

        # Build command (use per-phase python if provided)
        python_exe = python_override or self.python_executable
        cmd = [python_exe, str(script_path)] + args

        logger.info(f"Running phase {phase_id} ({phase_name}): {' '.join(cmd)}")

        # Create subprocess with streaming output
        try:
            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
                cwd=str(self.pipeline_dir)
            )

            # Stream output in background thread
            output_lines = []

            def stream_output():
                if self._current_process:
                    for line in iter(self._current_process.stdout.readline, ''):
                        if not line:
                            break
                        output_lines.append(line)
                        if progress_callback:
                            progress_callback(line.rstrip())

            stream_thread = threading.Thread(target=stream_output, daemon=True)
            stream_thread.start()

            # Wait for completion
            self._current_process.wait()
            stream_thread.join(timeout=2)

            exit_code = self._current_process.returncode
            duration = time.time() - start_time

            success = exit_code == 0 and not self._cancel_requested

            result = PhaseResult(
                phase_id=phase_id,
                phase_name=phase_name,
                success=success,
                exit_code=exit_code,
                duration_seconds=duration,
                output_dir=None
            )

            if not success:
                if self._cancel_requested:
                    result.error_message = "Phase cancelled by user"
                else:
                    result.error_message = f"Phase failed with exit code {exit_code}"
                logger.error(f"Phase {phase_id} failed: {result.error_message}")
            else:
                logger.info(f"Phase {phase_id} completed in {duration:.1f}s")

            return result

        except FileNotFoundError as e:
            duration = time.time() - start_time
            logger.error(f"Script not found: {script_path}")
            return PhaseResult(
                phase_id=phase_id,
                phase_name=phase_name,
                success=False,
                exit_code=-1,
                duration_seconds=duration,
                error_message=f"Script not found: {script_path}"
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.exception(f"Error running phase {phase_id}")
            return PhaseResult(
                phase_id=phase_id,
                phase_name=phase_name,
                success=False,
                exit_code=-1,
                duration_seconds=duration,
                error_message=str(e)
            )
        finally:
            self._current_process = None
            self._cancel_requested = False

    def cancel(self) -> None:
        """Cancel the currently running phase."""
        self._cancel_requested = True
        if self._current_process and self._current_process.poll() is None:
            logger.warning("Cancelling current phase...")
            try:
                # Try graceful termination first
                self._current_process.terminate()
                try:
                    self._current_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if not terminated
                    logger.warning("Force killing process...")
                    self._current_process.kill()
            except Exception as e:
                logger.error(f"Error cancelling process: {e}")
