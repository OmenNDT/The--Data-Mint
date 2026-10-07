"""
GPU Thermal Monitor

Monitors GPU temperature using nvidia-smi and pauses generation if temperature
exceeds threshold. Resumes when temperature drops below resume threshold.
"""

import subprocess
import time
from typing import Dict, Optional


class GPUThermalMonitor:
    """Monitors GPU temperature and implements thermal throttling."""

    def __init__(self, config: Dict):
        """
        Initialize thermal monitor.

        Args:
            config: Thermal config dict with max_temp_celsius, resume_temp_celsius, etc.
        """
        self.enabled = config.get("enabled", True)
        self.max_temp = config.get("max_temp_celsius", 85)
        self.resume_temp = config.get("resume_temp_celsius", 75)
        self.check_interval = config.get("check_interval_seconds", 30)

        self.is_paused = False
        self.last_check_time = 0

    def get_gpu_temperature(self) -> Optional[int]:
        """
        Get current GPU temperature via nvidia-smi.

        Returns:
            Temperature in Celsius or None if unavailable
        """
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                temp_str = result.stdout.strip()
                # Handle multiple GPUs (take first)
                if '\n' in temp_str:
                    temp_str = temp_str.split('\n')[0]
                return int(temp_str)
        except Exception as e:
            print(f"Warning: Failed to get GPU temp: {e}")
            return None

        return None

    def check_and_throttle(self) -> bool:
        """
        Check GPU temperature and pause if needed.
        Returns immediately if recently checked.

        Returns:
            True if generation should pause, False if OK to continue
        """
        if not self.enabled:
            return False

        current_time = time.time()

        # Skip check if recently checked (avoid overhead)
        if current_time - self.last_check_time < self.check_interval:
            return self.is_paused

        self.last_check_time = current_time

        temp = self.get_gpu_temperature()

        if temp is None:
            # Cannot read temp, assume OK
            return False

        # Check if need to pause
        if not self.is_paused and temp >= self.max_temp:
            print(f"\n⚠ GPU temperature {temp}°C >= {self.max_temp}°C")
            print(f"  Pausing generation until temp drops below {self.resume_temp}°C...")
            self.is_paused = True
            return True

        # Check if can resume
        if self.is_paused and temp <= self.resume_temp:
            print(f"\n✓ GPU temperature {temp}°C <= {self.resume_temp}°C")
            print(f"  Resuming generation...")
            self.is_paused = False
            return False

        # Still paused, wait
        if self.is_paused:
            print(f"  Waiting... GPU temp: {temp}°C (target: <={self.resume_temp}°C)")
            time.sleep(10)  # Wait 10s before next check
            return True

        return False

    def wait_until_cool(self):
        """Block until GPU temperature is within safe range."""
        if not self.enabled:
            return

        while True:
            temp = self.get_gpu_temperature()

            if temp is None:
                # Cannot read temp, assume OK
                return

            if temp <= self.resume_temp:
                return

            if not self.is_paused:
                print(f"\n⚠ GPU temperature {temp}°C >= {self.max_temp}°C")
                print(f"  Waiting for cooldown to {self.resume_temp}°C...")
                self.is_paused = True

            print(f"  Current temp: {temp}°C (target: <={self.resume_temp}°C)")
            time.sleep(10)

        self.is_paused = False

    def get_status(self) -> Dict:
        """
        Get current thermal status.

        Returns:
            Dict with temperature and paused status
        """
        temp = self.get_gpu_temperature()
        return {
            "temperature_celsius": temp,
            "is_paused": self.is_paused,
            "max_temp": self.max_temp,
            "resume_temp": self.resume_temp
        }
