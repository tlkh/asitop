import unittest
from unittest.mock import Mock, patch

from asitop.asitop import (
    _build_processor_widgets,
    _processor_title,
    _update_processor_widgets,
    main,
)
from asitop.parsers import parse_cpu_metrics, parse_gpu_metrics


def make_reading(timestamp):
    cpu_metrics = parse_cpu_metrics({
        "processor": {
            "clusters": [
                {
                    "name": "P0-Cluster",
                    "freq_hz": 2000e6,
                    "idle_ratio": 0.50,
                    "cpus": [{
                        "cpu": 0,
                        "freq_hz": 2000e6,
                        "idle_ratio": 0.75,
                    }],
                },
                {
                    "name": "S-Cluster",
                    "freq_hz": 4000e6,
                    "idle_ratio": 0.25,
                    "cpus": [{
                        "cpu": 1,
                        "freq_hz": 4000e6,
                        "idle_ratio": 0.50,
                    }],
                },
            ],
            "ane_energy": 0,
            "cpu_energy": 2000,
            "gpu_energy": 1000,
            "combined_power": 3000,
        }
    })
    gpu_metrics = parse_gpu_metrics({
        "gpu": {
            "freq_hz": 500,
            "idle_ratio": 0.75,
        }
    })
    return cpu_metrics, gpu_metrics, "Nominal", None, timestamp


class ProcessorWidgetTests(unittest.TestCase):
    def setUp(self):
        self.groups = make_reading(1)[0]["cluster_groups"]

    def test_widgets_follow_observed_cluster_families(self):
        _, group_gauges, core_gauges, _, _ = _build_processor_widgets(
            self.groups,
            color=2,
            show_cores=True,
        )

        self.assertEqual(["P", "S"], list(group_gauges))
        self.assertEqual([0], list(core_gauges["P"]))
        self.assertEqual([1], list(core_gauges["S"]))

    def test_widget_updates_use_matching_family_and_core(self):
        _, group_gauges, core_gauges, _, _ = _build_processor_widgets(
            self.groups,
            color=2,
            show_cores=True,
        )

        _update_processor_widgets(
            self.groups,
            group_gauges,
            core_gauges,
            show_cores=True,
        )

        self.assertEqual("P-CPU Usage: 25% @ 2000 MHz", group_gauges["P"].title)
        self.assertEqual(25, group_gauges["P"].value)
        self.assertEqual("S-CPU Usage: 50% @ 4000 MHz", group_gauges["S"].title)
        self.assertEqual("Core 2: 50%", core_gauges["S"][1].title)

    def test_processor_title_uses_observed_core_counts(self):
        self.assertEqual(
            "Apple M5 Pro (Cores: 1P+1S+20GPU)",
            _processor_title("Apple M5 Pro", self.groups, 20),
        )


class MainTests(unittest.TestCase):
    @patch("asitop.asitop.time.sleep")
    @patch("asitop.asitop.VSplit.display")
    @patch("asitop.asitop.clear_console")
    @patch("asitop.asitop.terminate_powermetrics_process")
    @patch("asitop.asitop.atexit.register")
    @patch("asitop.asitop.get_ram_metrics_dict")
    @patch("asitop.asitop.get_soc_info")
    @patch("asitop.asitop.parse_powermetrics")
    @patch("asitop.asitop.run_powermetrics_process")
    def test_main_renders_dynamic_groups_and_cleans_up(
        self,
        run_powermetrics,
        parse_powermetrics,
        get_soc_info,
        get_ram_metrics,
        register_exit_handler,
        terminate_powermetrics,
        clear_console,
        display,
        sleep,
    ):
        process = Mock()
        run_powermetrics.return_value = process
        parse_powermetrics.side_effect = [
            make_reading(1),
            make_reading(2),
            KeyboardInterrupt,
        ]
        get_soc_info.return_value = {
            "name": "Apple M5 Pro",
            "gpu_core_count": 20,
            "cpu_max_power": 20,
            "gpu_max_power": 20,
        }
        get_ram_metrics.return_value = {
            "used_GB": 10,
            "total_GB": 48,
            "free_percent": 21,
            "swap_total_GB": 0,
        }

        result = main([])

        self.assertEqual(0, result)
        display.assert_called_once()
        terminate_powermetrics.assert_called_with(process)
        register_exit_handler.assert_called_once()
        exit_handler = register_exit_handler.call_args.args[0]
        exit_handler()
        terminate_powermetrics.assert_called_with(process)


if __name__ == "__main__":
    unittest.main()
