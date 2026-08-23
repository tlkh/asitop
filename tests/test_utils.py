import os
import plistlib
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from asitop.utils import (
    parse_powermetrics,
    run_powermetrics_process,
    terminate_powermetrics_process,
)


class PowermetricsProcessTests(unittest.TestCase):
    @patch("asitop.utils.glob.glob", return_value=[])
    @patch("asitop.utils.os.geteuid", return_value=0)
    @patch("asitop.utils.subprocess.Popen")
    def test_root_process_does_not_nest_sudo(
        self,
        popen,
        get_euid,
        find_temp_files,
    ):
        process = Mock()
        popen.return_value = process

        result = run_powermetrics_process("123", nice=5, interval=2000)

        self.assertIs(process, result)
        command = popen.call_args.args[0]
        self.assertEqual("nice", command[0])
        self.assertNotIn("sudo", command)
        expected_output_path = str(Path(
            os.sep,
            "tmp",
            "asitop_powermetrics123",
        ))
        self.assertEqual([
            "nice", "-n", "5", "powermetrics",
            "--samplers", "cpu_power,gpu_power,thermal",
            "-o", expected_output_path,
            "-f", "plist", "-i", "2000",
        ], command)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    @patch("asitop.utils.glob.glob", return_value=[])
    @patch("asitop.utils.os.geteuid", return_value=501)
    @patch("asitop.utils.subprocess.Popen")
    def test_non_root_process_uses_sudo(
        self,
        popen,
        get_euid,
        find_temp_files,
    ):
        run_powermetrics_process("123")

        command = popen.call_args.args[0]
        self.assertEqual(["sudo", "nice"], command[:2])

    @patch("asitop.utils.os.killpg")
    def test_terminate_stops_the_process_group(self, kill_process_group):
        process = Mock(pid=123)
        process.poll.return_value = None

        terminate_powermetrics_process(process)

        kill_process_group.assert_called_once()
        self.assertEqual(123, kill_process_group.call_args.args[0])
        self.assertEqual(signal.SIGTERM, kill_process_group.call_args.args[1])

    @patch("asitop.utils.os.killpg")
    def test_terminate_ignores_an_exited_process(self, kill_process_group):
        process = Mock(pid=123)
        process.poll.return_value = 0

        terminate_powermetrics_process(process)

        kill_process_group.assert_not_called()


class ParsePowermetricsTests(unittest.TestCase):
    def make_sample(self, timestamp):
        return {
            "timestamp": timestamp,
            "thermal_pressure": "Nominal",
            "processor": {
                "clusters": [{
                    "name": "P-Cluster",
                    "freq_hz": 3000e6,
                    "idle_ratio": 0.5,
                    "cpus": [{
                        "cpu": 0,
                        "freq_hz": 3000e6,
                        "idle_ratio": 0.5,
                    }],
                }],
                "ane_energy": 0,
                "cpu_energy": 1000,
                "gpu_energy": 1000,
                "combined_power": 2000,
            },
            "gpu": {
                "freq_hz": 500,
                "idle_ratio": 0.75,
            },
        }

    def test_partial_trailing_sample_uses_latest_complete_sample(self):
        first_sample = plistlib.dumps(self.make_sample(1))
        second_sample = plistlib.dumps(self.make_sample(2))
        with tempfile.NamedTemporaryFile() as output:
            output.write(first_sample + b"\x00" + second_sample + b"\x00bplist")
            output.flush()

            reading = parse_powermetrics(path=output.name, timecode="")

        if reading is False:
            self.fail("Expected a complete powermetrics reading")
        self.assertEqual(2, reading[-1])
        self.assertEqual(50, reading[0]["P-Cluster_active"])

    def test_missing_file_returns_false(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            missing_file = Path(temp_directory, "missing")
            self.assertFalse(parse_powermetrics(
                path=str(missing_file),
                timecode="",
            ))


if __name__ == "__main__":
    unittest.main()
