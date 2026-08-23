import math
import unittest

from asitop.parsers import parse_cpu_metrics, parse_gpu_metrics


def make_cpu(cpu_id, active, frequency_mhz):
    return {
        "cpu": cpu_id,
        "freq_hz": frequency_mhz * 1e6,
        "idle_ratio": 1 - active / 100,
    }


def make_cluster(name, cpu_specs, active, frequency_mhz):
    return {
        "name": name,
        "freq_hz": frequency_mhz * 1e6,
        "idle_ratio": 1 - active / 100,
        "cpus": [make_cpu(*cpu_spec) for cpu_spec in cpu_specs],
    }


def make_sample(clusters):
    return {
        "processor": {
            "clusters": clusters,
            "ane_energy": 1000,
            "cpu_energy": 2000,
            "gpu_energy": 3000,
            "combined_power": 6000,
        }
    }


def groups_by_family(metrics):
    return {
        group["family"]: group
        for group in metrics["cluster_groups"]
    }


class ParseCpuMetricsTests(unittest.TestCase):
    def test_standard_e_and_p_clusters(self):
        metrics = parse_cpu_metrics(make_sample([
            make_cluster(
                "E-Cluster",
                [(0, 10, 1000), (1, 30, 1200)],
                40,
                1200,
            ),
            make_cluster(
                "P-Cluster",
                [(2, 50, 3000), (3, 70, 3200)],
                80,
                3200,
            ),
        ]))

        groups = groups_by_family(metrics)
        self.assertEqual(["E", "P"], list(groups))
        self.assertEqual(20, groups["E"]["active"])
        self.assertEqual(60, groups["P"]["active"])
        self.assertEqual([0, 1], metrics["e_core"])
        self.assertEqual([2, 3], metrics["p_core"])
        self.assertEqual(20, metrics["E-Cluster_active"])
        self.assertEqual(60, metrics["P-Cluster_active"])

    def test_numbered_clusters_are_grouped_and_weighted_by_core(self):
        metrics = parse_cpu_metrics(make_sample([
            make_cluster("E0-Cluster", [(0, 10, 1000)], 70, 1000),
            make_cluster("E1-Cluster", [(1, 30, 1200)], 80, 1200),
            make_cluster(
                "P0-Cluster",
                [(2, 20, 3000), (3, 40, 3200)],
                90,
                3200,
            ),
            make_cluster("P1-Cluster", [(4, 90, 3400)], 95, 3400),
        ]))

        groups = groups_by_family(metrics)
        self.assertEqual(20, groups["E"]["active"])
        self.assertEqual(50, groups["P"]["active"])
        self.assertEqual(1200, groups["E"]["freq_Mhz"])
        self.assertEqual(3400, groups["P"]["freq_Mhz"])
        self.assertEqual(3, groups["P"]["core_count"])

    def test_m5_p_and_s_clusters_remain_separate(self):
        metrics = parse_cpu_metrics(make_sample([
            make_cluster(
                "P0-Cluster",
                [(0, 10, 1500), (1, 30, 1700)],
                90,
                1700,
            ),
            make_cluster("P1-Cluster", [(2, 80, 3400)], 95, 3400),
            make_cluster(
                "S-Cluster",
                [(3, 50, 4200), (4, 70, 4400)],
                85,
                4400,
            ),
        ]))

        groups = groups_by_family(metrics)
        self.assertEqual(["P", "S"], list(groups))
        self.assertEqual(40, groups["P"]["active"])
        self.assertEqual(60, groups["S"]["active"])
        self.assertEqual([0, 1, 2], metrics["p_core"])
        self.assertEqual([], metrics["e_core"])
        self.assertEqual(0, metrics["E-Cluster_active"])

    def test_unified_m_cluster_keeps_its_own_family(self):
        metrics = parse_cpu_metrics(make_sample([
            make_cluster(
                "M0-Cluster",
                [(0, 25, 2500), (1, 75, 3500)],
                90,
                3500,
            ),
        ]))

        groups = groups_by_family(metrics)
        self.assertEqual(["M"], list(groups))
        self.assertEqual("M-CPU", groups["M"]["label"])
        self.assertEqual(50, groups["M"]["active"])
        self.assertEqual(50, metrics["M-Cluster_active"])

    def test_unknown_future_family_does_not_fall_into_p(self):
        metrics = parse_cpu_metrics(make_sample([
            make_cluster("Q7-Cluster", [(0, 35, 2800)], 60, 2800),
        ]))

        groups = groups_by_family(metrics)
        self.assertEqual(["Q"], list(groups))
        self.assertEqual(35, groups["Q"]["active"])
        self.assertEqual([], metrics["p_core"])

    def test_space_separated_cluster_name_is_classified(self):
        metrics = parse_cpu_metrics(make_sample([
            make_cluster("P0 Cluster", [(0, 35, 2800)], 60, 2800),
        ]))

        self.assertEqual(["P"], list(groups_by_family(metrics)))

    def test_cluster_metrics_are_used_when_core_metrics_are_absent(self):
        metrics = parse_cpu_metrics(make_sample([
            make_cluster("P0-Cluster", [], 20, 2000),
            make_cluster("P1-Cluster", [], 60, 3000),
        ]))

        group = groups_by_family(metrics)["P"]
        self.assertEqual(40, group["active"])
        self.assertEqual(3000, group["freq_Mhz"])

    def test_active_ratio_accounts_for_down_time(self):
        payload = make_sample([{
            "name": "P-Cluster",
            "freq_hz": 3000e6,
            "active_ratio": 0.25,
            "idle_ratio": 0.50,
            "down_ratio": 0.25,
            "cpus": [{
                "cpu": 0,
                "freq_hz": 3000e6,
                "idle_ratio": 0.50,
                "down_ratio": 0.25,
            }],
        }])

        group = groups_by_family(parse_cpu_metrics(payload))["P"]
        self.assertEqual(25, group["active"])

    def test_non_finite_ratios_and_frequencies_use_safe_defaults(self):
        payload = make_sample([{
            "name": "Performance Cluster",
            "freq_hz": math.nan,
            "idle_ratio": math.nan,
            "cpus": [{
                "cpu": 0,
                "freq_hz": math.nan,
                "idle_ratio": math.nan,
            }],
        }])

        group = groups_by_family(parse_cpu_metrics(payload))["P"]
        self.assertEqual(0, group["active"])
        self.assertEqual(0, group["freq_Mhz"])


class ParseGpuMetricsTests(unittest.TestCase):
    def test_gpu_down_time_is_not_counted_as_active(self):
        metrics = parse_gpu_metrics({
            "gpu": {
                "freq_hz": 500,
                "idle_ratio": 0.50,
                "down_ratio": 0.25,
            }
        })

        self.assertEqual(25, metrics["active"])
        self.assertEqual(500, metrics["freq_MHz"])

    def test_non_finite_gpu_values_use_safe_defaults(self):
        metrics = parse_gpu_metrics({
            "gpu": {
                "freq_hz": math.nan,
                "idle_ratio": math.nan,
            }
        })

        self.assertEqual(0, metrics["active"])
        self.assertEqual(0, metrics["freq_MHz"])


if __name__ == "__main__":
    unittest.main()
