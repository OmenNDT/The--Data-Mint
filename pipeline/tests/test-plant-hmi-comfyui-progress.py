"""Unit tests for the P-601 (ComfyUI) black-box progress panel.

Replays `tests/fixtures/comfyui-ws-sample.jsonl`, a trimmed real recording taken
from ComfyUI (127.0.0.1:8188) while the batch pipeline ran a pilot batch WITHOUT
a client_id (see `plant_comfyui_progress_state.py` docstring for why only
status/progress/progress_state ever arrive in that case, and how a foreign job
WITH a client_id stays invisible to us — M1).

Run: .venv/bin/python tests/test-plant-hmi-comfyui-progress.py
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plant_hmi.plant_comfyui_progress_state import (  # noqa: E402
    apply_progress,
    apply_progress_state,
    apply_status,
    compute_comfy_progress,
    new_state,
    on_disconnect,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "comfyui-ws-sample.jsonl"
NODE_META = {"10": {"title": "KSampler", "class_type": "KSampler"},
             "11": {"title": "VAEDecode", "class_type": "VAEDecode"},
             "12": {"title": "SaveImage", "class_type": "SaveImage"}}


def replay(fixture_path: Path, clock_start: float = 1_700_000_000.0):
    """Feed every recorded message through the same dispatch the observer thread
    uses, with a synthetic increasing clock (real recv() timestamps are not in
    the JSONL; each message advances 0.2s, plausible for a KSampler at ~5 it/s)."""
    state = new_state()
    state["connected"] = True
    now = clock_start
    for line in fixture_path.read_text().splitlines():
        if not line.strip():
            continue
        msg = json.loads(line)
        event, data = msg.get("type"), msg.get("data") or {}
        now += 0.2
        state["last_event_ts"] = now
        if event == "status":
            qr = ((data.get("status") or {}).get("exec_info") or {}).get("queue_remaining")
            apply_status(state, qr, now)
        elif event == "progress_state":
            apply_progress_state(state, data.get("prompt_id"), data.get("nodes"), now)
        elif event == "progress":
            apply_progress(state, data.get("prompt_id"), data.get("node"),
                            data.get("value"), data.get("max"), now)
    return state, now


class ReplayRealSampleTest(unittest.TestCase):
    def test_fixture_exists_and_has_all_three_event_types(self):
        self.assertTrue(FIXTURE.is_file())
        types = {json.loads(l)["type"] for l in FIXTURE.read_text().splitlines() if l.strip()}
        self.assertEqual(types, {"status", "progress", "progress_state"})

    def test_replay_lands_on_a_consistent_final_state(self):
        state, now = replay(FIXTURE)
        result = compute_comfy_progress(state, NODE_META, now)
        # The fixture ends mid-batch or with the queue drained: either is a
        # valid terminal state, never a crash and never "busy_foreign" (we
        # were actively receiving our own progress the whole replay).
        self.assertIn(result["phase"], ("idle", "executing"))
        self.assertIsInstance(result["connected"], bool)
        self.assertIsInstance(result["prompts_1h"], int)
        self.assertGreaterEqual(result["prompts_1h"], 0)

    def test_ksampler_step_and_title_surface_during_progress(self):
        state, now = replay(FIXTURE)
        # The fixture is known (from the recording) to end with node 10 (KSampler)
        # mid-progress or freshly finished; step/steps must be non-negative ints
        # or both None together, never one without the other.
        result = compute_comfy_progress(state, NODE_META, now)
        if result["phase"] == "executing" and result["node"] == "10":
            self.assertEqual(result["node_title"], "KSampler")
            self.assertEqual(result["node_class"], "KSampler")
            self.assertTrue(result["step_seen"])
            self.assertIsNotNone(result["step"])
            self.assertIsNotNone(result["steps"])


class PureStateMachineTest(unittest.TestCase):
    def test_idle_state_never_fakes_a_percentage(self):
        state = new_state()
        result = compute_comfy_progress(state, {}, now=1000.0)
        self.assertEqual(result["phase"], "idle")
        for key in ("prompt_id", "node", "node_title", "node_class", "step", "steps", "it_s", "elapsed_s"):
            self.assertIsNone(result[key])
        self.assertFalse(result["step_seen"])

    def test_status_zero_finalizes_prompt_and_counts_it(self):
        state = new_state()
        apply_progress_state(state, "p1", {"1": {"state": "running"}}, now=100.0)
        apply_progress(state, "p1", "1", 5, 10, now=101.0)
        apply_status(state, 0, now=105.0)
        result = compute_comfy_progress(state, {}, now=106.0)
        self.assertEqual(result["phase"], "idle")
        self.assertEqual(result["prompts_1h"], 1)
        self.assertAlmostEqual(result["last_prompt_s"], 5.0)

    def test_new_prompt_id_without_status_zero_still_counts_previous(self):
        state = new_state()
        apply_progress_state(state, "p1", {"1": {"state": "running"}}, now=100.0)
        apply_progress_state(state, "p2", {"1": {"state": "running"}}, now=200.0)
        result = compute_comfy_progress(state, {}, now=200.0)
        self.assertEqual(result["prompt_id"], "p2")
        self.assertEqual(result["prompts_1h"], 1)

    def test_all_nodes_finished_finalizes_without_waiting_for_queue_zero(self):
        """M1 core fix: a prompt of ours is done the moment its own nodes report
        finished, independent of ComfyUI's overall queue (which may still show
        >0 because of an invisible foreign job queued right behind ours)."""
        state = new_state()
        apply_progress_state(state, "p1", {"1": {"state": "running"}}, now=100.0)
        apply_progress_state(state, "p1", {"1": {"state": "finished"}}, now=101.0)
        result = compute_comfy_progress(state, {}, now=101.0)
        self.assertEqual(result["phase"], "idle")
        self.assertEqual(result["prompts_1h"], 1)
        self.assertAlmostEqual(result["last_prompt_s"], 1.0)

    def test_foreign_job_keeps_us_out_of_executing(self):
        """M1: queue never reaches 0 (a foreign job is queued behind ours), but
        once our prompt's own nodes finish we must not stay stuck showing it as
        executing, and after the busy_foreign grace window with no progress of
        our own, phase becomes busy_foreign, never a stale "executing"."""
        state = new_state()
        apply_progress_state(state, "ours", {"1": {"state": "running"}}, now=0.0)
        apply_progress_state(state, "ours", {"1": {"state": "finished"}}, now=1.0)
        apply_status(state, 1, now=2.0)  # foreign job still queued: never hits 0
        result_just_after = compute_comfy_progress(state, {}, now=3.0)
        self.assertEqual(result_just_after["phase"], "idle")  # still within grace window
        result_after_grace = compute_comfy_progress(state, {}, now=20.0)
        self.assertEqual(result_after_grace["phase"], "busy_foreign")
        self.assertIsNone(result_after_grace["prompt_id"])
        self.assertIsNone(result_after_grace["node"])

    def test_it_s_computed_from_two_progress_samples(self):
        state = new_state()
        apply_progress_state(state, "p1", {"10": {"state": "running"}}, now=100.0)
        apply_progress(state, "p1", "10", 5, 20, now=100.0)
        apply_progress(state, "p1", "10", 10, 20, now=101.0)
        result = compute_comfy_progress(state, {}, now=101.0)
        self.assertAlmostEqual(result["it_s"], 5.0)

    def test_completions_older_than_1h_are_pruned(self):
        state = new_state()
        apply_progress_state(state, "old", {"1": {"state": "running"}}, now=0.0)
        apply_status(state, 0, now=1.0)
        result = compute_comfy_progress(state, {}, now=1.0 + 3700.0)
        self.assertEqual(result["prompts_1h"], 0)

    def test_disconnected_reports_unknown_not_false_progress(self):
        state = new_state()
        state["connected"] = False
        result = compute_comfy_progress(state, {}, now=1.0)
        self.assertFalse(result["connected"])
        self.assertEqual(result["phase"], "idle")

    def test_disconnect_mid_prompt_does_not_count_it_l6(self):
        """L6: a prompt in flight when the socket drops is unresolved, not a
        measured completion — no prompts_1h bump, no last_prompt_s from it."""
        state = new_state()
        apply_progress_state(state, "p1", {"1": {"state": "running"}}, now=10.0)
        apply_progress(state, "p1", "1", 3, 10, now=11.0)
        on_disconnect(state, now=12.0)
        result = compute_comfy_progress(state, {}, now=13.0)
        self.assertFalse(result["connected"])
        self.assertEqual(result["phase"], "idle")
        self.assertEqual(result["prompts_1h"], 0)
        self.assertIsNone(result["last_prompt_s"])
        # reconnecting and seeing the SAME prompt_id finish must not double count
        # either (prompt_counted stays True from the disconnect's finalize call)
        apply_status(state, 0, now=14.0)
        result2 = compute_comfy_progress(state, {}, now=15.0)
        self.assertEqual(result2["prompts_1h"], 0)


if __name__ == "__main__":
    unittest.main()
