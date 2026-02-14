# Mock Subprocess Patterns for Pipeline UI Testing

**Research Focus:** Python mocking for testing pipeline UIs without real processes
**Date:** 2026-02-13

## 1. Mocking subprocess.Popen with Streaming Stdout

### Core Pattern - unittest.mock
```python
from unittest.mock import Mock, patch
import io

# Mock Popen with streaming stdout
mock_process = Mock()
mock_process.stdout = io.StringIO("Line 1\nLine 2\nLine 3\n")
mock_process.returncode = 0
mock_process.poll.return_value = None  # Still running

with patch('subprocess.Popen', return_value=mock_process):
    # Test code that reads stdout
```

### Streaming Iterator Pattern
```python
# Create line-by-line iterator for readline()
mock_stdout = Mock()
mock_stdout.readline.side_effect = [
    b"Processing step 1...\n",
    b"Processing step 2...\n",
    b"Complete!\n",
    b""  # EOF
]
mock_process.stdout = mock_stdout
```

### Libraries for Subprocess Mocking
- **pytest-subprocess**: Plugin specifically for subprocess, hooks Popen(), supports streaming via list of lines
- **testfixtures.MockPopen**: File-like stdout/stderr objects, use `set_command()` for behavior, `all_calls` for assertions
- **MockProc**: Stub subprocesses, test timeout/output/input handling

## 2. Fake Progress Output Simulation

### Real-time Progress Pattern
```python
import threading
import queue
import time

class FakeProgressStream:
    """Simulates long-running process with progress"""
    def __init__(self, duration=5):
        self.queue = queue.Queue()
        self.duration = duration

    def readline(self):
        try:
            return self.queue.get(timeout=0.1)
        except queue.Empty:
            return b""

    def start(self):
        def emit_progress():
            steps = ["Init...", "Processing...", "Finalizing...", "Done!"]
            for i, step in enumerate(steps):
                time.sleep(self.duration / len(steps))
                self.queue.put(f"[{i+1}/{len(steps)}] {step}\n".encode())
            self.queue.put(b"")  # EOF

        threading.Thread(target=emit_progress, daemon=True).start()

# Usage
fake_stream = FakeProgressStream(duration=2)
fake_stream.start()
mock_process.stdout = fake_stream
```

### Progress Percentage Pattern
```python
# side_effect with callable for dynamic output
def progress_generator():
    for i in range(0, 101, 10):
        yield f"Progress: {i}%\n".encode()
    yield b""  # EOF

mock_stdout.readline.side_effect = progress_generator()
```

## 3. Testing Long-Running Process UIs

### Time Acceleration Pattern
```python
# Mock time.sleep to speed up tests
with patch('time.sleep'):
    # Test runs instantly but code behavior preserved
    run_pipeline_ui()
```

### Process State Simulation
```python
class MockProcess:
    """Simulates process lifecycle"""
    def __init__(self, lines, delay=0.1):
        self.lines = iter(lines)
        self.delay = delay
        self.returncode = None
        self._running = True

    def poll(self):
        """None = running, 0 = success, >0 = error"""
        if self._running:
            return None
        return self.returncode

    def readline(self):
        try:
            time.sleep(self.delay)
            return next(self.lines).encode() + b"\n"
        except StopIteration:
            self._running = False
            self.returncode = 0
            return b""
```

### Async UI Update Testing
```python
# Test GUI updates during process execution
mock_process = Mock()
lines = ["Step 1", "Step 2", "Step 3"]
mock_process.stdout.readline.side_effect = [l.encode()+b"\n" for l in lines] + [b""]

with patch('subprocess.Popen', return_value=mock_process):
    ui = PipelineUI()
    ui.run_pipeline()

    # Verify UI was updated for each line
    assert ui.log_widget.get("1.0", "end").count("Step") == 3
```

## 4. Mocking tkinter Dialogs (Headless Testing)

### File Dialog Pattern
```python
from unittest.mock import patch

# Mock askopenfilename to return test path
@patch('tkinter.filedialog.askopenfilename')
def test_file_selection(mock_dialog):
    mock_dialog.return_value = '/path/to/test/file.csv'

    ui = MyUI()
    ui.select_file_button.invoke()

    assert ui.selected_file == '/path/to/test/file.csv'
    mock_dialog.assert_called_once()

# Mock askdirectory
@patch('tkinter.filedialog.askdirectory')
def test_folder_selection(mock_dialog):
    mock_dialog.return_value = '/test/output/dir'
    # Test code
```

### Patch Location Critical
```python
# WRONG: Patch where defined
@patch('tkinter.filedialog.askopenfilename')

# CORRECT: Patch where imported/used
@patch('my_ui_module.askopenfilename')
# If imported as: from tkinter.filedialog import askopenfilename
```

### Headless Testing Strategies
- **Mock widgets/methods**: Avoid full GUI rendering in unit tests
- **PyAutoGUI + Xvfb**: For integration tests requiring real rendering (Linux)
- **pytest fixtures**: Set up mock dialogs consistently across tests
- **unittest.mock preferred**: More control than trying to automate real dialogs

## 5. Error Handling UI Testing

### Exception Injection Pattern
```python
# side_effect with exception class/instance
mock_process = Mock()
mock_process.communicate.side_effect = subprocess.TimeoutExpired(
    cmd='test', timeout=5
)

with patch('subprocess.Popen', return_value=mock_process):
    ui.run_pipeline()
    # Verify error displayed to user
    assert "Timeout" in ui.error_label.cget("text")
```

### Multiple Failure Scenarios
```python
test_cases = [
    (FileNotFoundError("Config missing"), "Config file not found"),
    (PermissionError("Access denied"), "Permission denied"),
    (subprocess.CalledProcessError(1, 'cmd'), "Process failed"),
]

for exception, expected_msg in test_cases:
    with patch('subprocess.Popen', side_effect=exception):
        ui.run_pipeline()
        assert expected_msg in ui.get_error_message()
```

### Partial Failure Pattern
```python
# Process runs then fails mid-stream
def failing_readline():
    yield b"Starting...\n"
    yield b"Processing...\n"
    raise IOError("Connection lost")

mock_stdout.readline.side_effect = failing_readline()
# Test UI handles interruption gracefully
```

### UI State Verification
```python
# Verify error UI elements displayed
def test_error_display():
    mock_process.returncode = 1
    mock_process.stderr.read.return_value = b"Fatal error"

    with patch('subprocess.Popen', return_value=mock_process):
        ui.run()

    assert ui.error_frame.winfo_ismapped()  # Error UI visible
    assert "Fatal error" in ui.error_text.get("1.0", "end")
    assert ui.retry_button.winfo_ismapped()  # Retry option shown
```

## Best Practices Summary

1. **Use pytest-subprocess** for complex subprocess mocking (cleaner than manual mocks)
2. **Mock at import location** not definition location (critical for tkinter dialogs)
3. **side_effect** versatile: exceptions, generators, callables
4. **Mock time.sleep** for fast tests of long-running UIs
5. **Test error paths** as thoroughly as happy paths
6. **Verify UI state changes** not just function calls
7. **Use iterators/generators** for realistic streaming output
8. **Separate unit tests** (mocked) from integration tests (real subprocesses)

## Unresolved Questions

1. Best pattern for testing tkinter .after() delayed callbacks with mocks?
2. How to test UI responsiveness (threading) without adding delays to tests?
3. Recommended assertion library for tkinter widget state verification?

## Sources

- [pytest-subprocess](https://pypi.org/project/pytest-subprocess/)
- [testfixtures MockPopen](https://testfixtures.readthedocs.io/en/latest/popen.html)
- [MockProc](https://pythonhosted.org/MockProc/)
- [unittest.mock docs](https://docs.python.org/3/library/unittest.mock.html)
- [Real Python Mock Guide](https://realpython.com/python-mock-library/)
- [Testing Tkinter Headless](https://gist.github.com/howardrotterdam/63c06754d9f7e1b1fa2c390be6319a44)
- [Robust Tkinter Testing](https://code.activestate.com/recipes/578964-robust-testing-of-tkinter-menu-items-with-mocking/)
- [Subprocess Streaming](https://alexwlchan.net/til/2025/subprocess-line-by-line/)
- [Mock Exceptions Guide](https://pytest-with-eric.com/mocking/python-magicmock-raise-exception/)
