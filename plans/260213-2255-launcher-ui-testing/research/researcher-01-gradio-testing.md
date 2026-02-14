# Gradio UI Testing Patterns

**Research Focus:** Testing Gradio apps programmatically and visually
**Date:** 2026-02-13

## Gradio Testing Approaches

### 1. gradio_client (Python Client)
- `Client("http://localhost:7860")` connects to running app
- `.predict()` calls endpoints synchronously
- `.submit()` for async/non-blocking calls, returns Job object
- `.view_api()` inspects available endpoints

### 2. launch() for Testing
- `app.launch(prevent_thread_lock=True)` — non-blocking, allows test code after launch
- `app.launch(share=False)` — local only
- `app.close()` — clean shutdown after tests
- Pattern: launch → test → close in try/finally

### 3. Playwright (Visual Testing)
- Gradio officially uses Playwright for frontend tests
- Retrying assertions for async UI: `await expect(element).toBeChecked()`
- Trace viewer for debugging: `npx playwright show-trace`
- Auto-generate test skeletons: `npx playwright codegen <url>`
- Prefer visible UI changes over internal request tracking

### 4. unittest.mock for Event Handlers
- Mock subprocess.Popen to simulate pipeline
- Mock tkinter.filedialog.askdirectory for folder browse
- side_effect for streaming stdout simulation
- Patch at import location, not definition

### 5. Key Patterns
- `prevent_thread_lock=True` + `share=False` for pytest
- Generator functions (yield) testable via iterating results
- Queue-based log streaming testable with mock Queue
- Background thread testing: mock threading.Thread or use real threads with short timeout

## Recommended Stack for This Project
- **Visual testing**: Launch Gradio manually, observe in browser
- **Unit tests**: pytest + unittest.mock (mock subprocess, tkinter)
- **API testing**: gradio_client for endpoint validation
- **No Playwright needed** — overkill for internal tool; manual visual + unit tests sufficient

## Sources
- [Gradio Python Client Docs](https://www.gradio.app/guides/getting-started-with-the-python-client)
- [Gradio Playwright Guidelines](https://github.com/gradio-app/gradio/tree/main/testing-guidelines)
- [Gradio Blocks API](https://www.gradio.app/docs/gradio/blocks)
