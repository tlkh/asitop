def parse_thermal_pressure(powermetrics_parse):
    return powermetrics_parse["thermal_pressure"]


def _true_idle_percent(node):
    if "idle_ratio" in node:
        return int(float(node["idle_ratio"]) * 100)

    active = float(node.get("active_ratio", 0))
    down = float(node.get("down_ratio", 0))
    idle = 1 - active - down
    if idle < 0:
        idle = 0
    return int(idle * 100)


def parse_bandwidth_metrics(powermetrics_parse):
    bandwidth_metrics = powermetrics_parse.get("bandwidth_counters", [])
    bandwidth_metrics_dict = {}

    data_fields = [
        "PCPU0 DCS RD", "PCPU0 DCS WR",
        "PCPU1 DCS RD", "PCPU1 DCS WR",
        "PCPU2 DCS RD", "PCPU2 DCS WR",
        "PCPU3 DCS RD", "PCPU3 DCS WR",
        "PCPU DCS RD", "PCPU DCS WR",
        "ECPU0 DCS RD", "ECPU0 DCS WR",
        "ECPU1 DCS RD", "ECPU1 DCS WR",
        "ECPU DCS RD", "ECPU DCS WR",
        "GFX DCS RD", "GFX DCS WR",
        "ISP DCS RD", "ISP DCS WR",
        "STRM CODEC DCS RD", "STRM CODEC DCS WR",
        "PRORES DCS RD", "PRORES DCS WR",
        "VDEC DCS RD", "VDEC DCS WR",
        "VENC0 DCS RD", "VENC0 DCS WR",
        "VENC1 DCS RD", "VENC1 DCS WR",
        "VENC2 DCS RD", "VENC2 DCS WR",
        "VENC3 DCS RD", "VENC3 DCS WR",
        "VENC DCS RD", "VENC DCS WR",
        "JPG0 DCS RD", "JPG0 DCS WR",
        "JPG1 DCS RD", "JPG1 DCS WR",
        "JPG2 DCS RD", "JPG2 DCS WR",
        "JPG3 DCS RD", "JPG3 DCS WR",
        "JPG DCS RD", "JPG DCS WR",
        "DCS RD", "DCS WR",
    ]

    for h in data_fields:
        bandwidth_metrics_dict[h] = 0

    for l in bandwidth_metrics:
        if l.get("name") in data_fields:
            bandwidth_metrics_dict[l["name"]] = l["value"] / 1e9

    bandwidth_metrics_dict["PCPU DCS RD"] = (
        bandwidth_metrics_dict["PCPU DCS RD"]
        + bandwidth_metrics_dict["PCPU0 DCS RD"]
        + bandwidth_metrics_dict["PCPU1 DCS RD"]
        + bandwidth_metrics_dict["PCPU2 DCS RD"]
        + bandwidth_metrics_dict["PCPU3 DCS RD"]
    )
    bandwidth_metrics_dict["PCPU DCS WR"] = (
        bandwidth_metrics_dict["PCPU DCS WR"]
        + bandwidth_metrics_dict["PCPU0 DCS WR"]
        + bandwidth_metrics_dict["PCPU1 DCS WR"]
        + bandwidth_metrics_dict["PCPU2 DCS WR"]
        + bandwidth_metrics_dict["PCPU3 DCS WR"]
    )

    bandwidth_metrics_dict["JPG DCS RD"] = (
        bandwidth_metrics_dict["JPG DCS RD"]
        + bandwidth_metrics_dict["JPG0 DCS RD"]
        + bandwidth_metrics_dict["JPG1 DCS RD"]
        + bandwidth_metrics_dict["JPG2 DCS RD"]
        + bandwidth_metrics_dict["JPG3 DCS RD"]
    )
    bandwidth_metrics_dict["JPG DCS WR"] = (
        bandwidth_metrics_dict["JPG DCS WR"]
        + bandwidth_metrics_dict["JPG0 DCS WR"]
        + bandwidth_metrics_dict["JPG1 DCS WR"]
        + bandwidth_metrics_dict["JPG2 DCS WR"]
        + bandwidth_metrics_dict["JPG3 DCS WR"]
    )

    bandwidth_metrics_dict["VENC DCS RD"] = (
        bandwidth_metrics_dict["VENC DCS RD"]
        + bandwidth_metrics_dict["VENC0 DCS RD"]
        + bandwidth_metrics_dict["VENC1 DCS RD"]
        + bandwidth_metrics_dict["VENC2 DCS RD"]
        + bandwidth_metrics_dict["VENC3 DCS RD"]
    )
    bandwidth_metrics_dict["VENC DCS WR"] = (
        bandwidth_metrics_dict["VENC DCS WR"]
        + bandwidth_metrics_dict["VENC0 DCS WR"]
        + bandwidth_metrics_dict["VENC1 DCS WR"]
        + bandwidth_metrics_dict["VENC2 DCS WR"]
        + bandwidth_metrics_dict["VENC3 DCS WR"]
    )

    bandwidth_metrics_dict["MEDIA DCS"] = sum([
        bandwidth_metrics_dict["ISP DCS RD"],
        bandwidth_metrics_dict["ISP DCS WR"],
        bandwidth_metrics_dict["STRM CODEC DCS RD"],
        bandwidth_metrics_dict["STRM CODEC DCS WR"],
        bandwidth_metrics_dict["PRORES DCS RD"],
        bandwidth_metrics_dict["PRORES DCS WR"],
        bandwidth_metrics_dict["VDEC DCS RD"],
        bandwidth_metrics_dict["VDEC DCS WR"],
        bandwidth_metrics_dict["VENC DCS RD"],
        bandwidth_metrics_dict["VENC DCS WR"],
        bandwidth_metrics_dict["JPG DCS RD"],
        bandwidth_metrics_dict["JPG DCS WR"],
    ])

    return bandwidth_metrics_dict


def _ratio_to_percent(x):
    return int(float(x) * 100)


def _true_active_percent(node):
    if "active_ratio" in node:
        return int(float(node["active_ratio"]) * 100)

    idle = float(node.get("idle_ratio", 0))
    down = float(node.get("down_ratio", 0))
    active = 1 - idle - down
    if active < 0:
        active = 0
    return int(active * 100)


def _avg(vals):
    if not vals:
        return 0
    return int(sum(vals) / len(vals))


def _max(vals):
    if not vals:
        return 0
    return int(max(vals))


def _cluster_cpus(cluster):
    return [c.get("cpu") for c in cluster.get("cpus", []) if "cpu" in c]


def _cluster_down_percent(cluster):
    if "down_ratio" in cluster:
        return int(float(cluster["down_ratio"]) * 100)
    return 0


def _cluster_cpu_avg(cluster, fn):
    cpus = cluster.get("cpus", [])
    if not cpus:
        return 0
    return int(sum(fn(cpu) for cpu in cpus) / len(cpus))


def _classify_cluster(cluster):
    """
    Return 'P', 'S', or 'E'.

    Rules:
    - P0/P1/... / PERFORMANCE => P
    - S-Cluster / S...        => S
    - E... / EFFICIENCY       => E
    - fallback                => P
    """
    name = cluster.get("name", "").strip().upper()

    if name.startswith("S"):
        return "S"

    if name.startswith("P") or "PERFORMANCE" in name:
        return "P"

    if name.startswith("E") or "EFFICIENCY" in name:
        return "E"

    return "P"


def parse_cpu_metrics(powermetrics_parse):
    e_core = []
    p_core = []
    s_core = []

    cpu_metrics = powermetrics_parse["processor"]
    cpu_metric_dict = {}
    cpu_clusters = cpu_metrics["clusters"]

    e_cluster_names = []
    p_cluster_names = []
    s_cluster_names = []

    cluster_map = {}

    for cluster in cpu_clusters:
        cluster_name = cluster["name"]
        cluster_type = _classify_cluster(cluster)

        cluster_freq = int(cluster["freq_hz"] / 1e6)

        # 原始 cluster 级别（HW residency）
        cluster_hw_active = _true_active_percent(cluster)
        cluster_hw_idle = _true_idle_percent(cluster)
        cluster_hw_down = _cluster_down_percent(cluster)

        # 你真正想看的：该 cluster 内每个 CPU 的平均 active/idle/down
        cluster_cpu_active_avg = _cluster_cpu_avg(cluster, _true_active_percent)
        cluster_cpu_idle_avg = _cluster_cpu_avg(cluster, _true_idle_percent)
        cluster_cpu_down_avg = _cluster_cpu_avg(
            cluster, lambda cpu: int(float(cpu.get("down_ratio", 0)) * 100)
        )

        cpu_metric_dict[f"{cluster_name}_freq_Mhz"] = cluster_freq

        # 保留原始 cluster-level 指标
        cpu_metric_dict[f"{cluster_name}_hw_active"] = cluster_hw_active
        cpu_metric_dict[f"{cluster_name}_hw_idle"] = cluster_hw_idle
        cpu_metric_dict[f"{cluster_name}_hw_down"] = cluster_hw_down

        # cluster 的 active/idle/down 统一改成“core 平均”
        cpu_metric_dict[f"{cluster_name}_active"] = cluster_cpu_active_avg
        cpu_metric_dict[f"{cluster_name}_idle"] = cluster_cpu_idle_avg
        cpu_metric_dict[f"{cluster_name}_down"] = cluster_cpu_down_avg

        cluster_map[cluster_name] = {
            "type": cluster_type,
            "cpus": _cluster_cpus(cluster),
            "freq_Mhz": cluster_freq,
            "hw_active": cluster_hw_active,
            "hw_idle": cluster_hw_idle,
            "hw_down": cluster_hw_down,
            "active": cluster_cpu_active_avg,
            "idle": cluster_cpu_idle_avg,
            "down": cluster_cpu_down_avg,
        }

        if cluster_type == "E":
            e_cluster_names.append(cluster_name)
            logical_prefix = "E-Cluster"
            core_bucket = e_core
        elif cluster_type == "S":
            s_cluster_names.append(cluster_name)
            logical_prefix = "S-Cluster"
            core_bucket = s_core
        else:
            p_cluster_names.append(cluster_name)
            logical_prefix = "P-Cluster"
            core_bucket = p_core

        for cpu in cluster["cpus"]:
            cpu_id = cpu["cpu"]
            core_bucket.append(cpu_id)

            cpu_metric_dict[f"{logical_prefix}{cpu_id}_freq_Mhz"] = int(cpu["freq_hz"] / 1e6)
            cpu_metric_dict[f"{logical_prefix}{cpu_id}_active"] = _true_active_percent(cpu)
            cpu_metric_dict[f"{logical_prefix}{cpu_id}_idle"] = _true_idle_percent(cpu)
            cpu_metric_dict[f"{logical_prefix}{cpu_id}_down"] = int(float(cpu.get("down_ratio", 0)) * 100)

    e_core = sorted(set(e_core))
    p_core = sorted(set(p_core))
    s_core = sorted(set(s_core))

    cpu_metric_dict["e_core"] = e_core
    cpu_metric_dict["p_core"] = p_core
    cpu_metric_dict["s_core"] = s_core
    cpu_metric_dict["cluster_map"] = cluster_map

    cpu_metric_dict["has_e_cluster"] = len(e_cluster_names) > 0
    cpu_metric_dict["has_p_cluster"] = len(p_cluster_names) > 0
    cpu_metric_dict["has_s_cluster"] = len(s_cluster_names) > 0

    cpu_metric_dict["E-Cluster_active"] = _avg(
        [cpu_metric_dict[f"{name}_active"] for name in e_cluster_names if f"{name}_active" in cpu_metric_dict]
    )
    cpu_metric_dict["E-Cluster_idle"] = _avg(
        [cpu_metric_dict[f"{name}_idle"] for name in e_cluster_names if f"{name}_idle" in cpu_metric_dict]
    )
    cpu_metric_dict["E-Cluster_freq_Mhz"] = _max(
        [cpu_metric_dict[f"{name}_freq_Mhz"] for name in e_cluster_names if f"{name}_freq_Mhz" in cpu_metric_dict]
    )
    cpu_metric_dict["E-Cluster_down"] = _avg(
        [cpu_metric_dict[f"{name}_down"] for name in e_cluster_names if f"{name}_down" in cpu_metric_dict]
    )

    cpu_metric_dict["P-Cluster_active"] = _avg(
        [cpu_metric_dict[f"{name}_active"] for name in p_cluster_names if f"{name}_active" in cpu_metric_dict]
    )
    cpu_metric_dict["P-Cluster_idle"] = _avg(
        [cpu_metric_dict[f"{name}_idle"] for name in p_cluster_names if f"{name}_idle" in cpu_metric_dict]
    )
    cpu_metric_dict["P-Cluster_freq_Mhz"] = _max(
        [cpu_metric_dict[f"{name}_freq_Mhz"] for name in p_cluster_names if f"{name}_freq_Mhz" in cpu_metric_dict]
    )
    cpu_metric_dict["P-Cluster_down"] = _avg(
        [cpu_metric_dict[f"{name}_down"] for name in p_cluster_names if f"{name}_down" in cpu_metric_dict]
    )

    cpu_metric_dict["S-Cluster_active"] = _avg(
        [cpu_metric_dict[f"{name}_active"] for name in s_cluster_names if f"{name}_active" in cpu_metric_dict]
    )
    cpu_metric_dict["S-Cluster_idle"] = _avg(
        [cpu_metric_dict[f"{name}_idle"] for name in s_cluster_names if f"{name}_idle" in cpu_metric_dict]
    )
    cpu_metric_dict["S-Cluster_freq_Mhz"] = _max(
        [cpu_metric_dict[f"{name}_freq_Mhz"] for name in s_cluster_names if f"{name}_freq_Mhz" in cpu_metric_dict]
    )
    cpu_metric_dict["S-Cluster_down"] = _avg(
        [cpu_metric_dict[f"{name}_down"] for name in s_cluster_names if f"{name}_down" in cpu_metric_dict]
    )

    cpu_metric_dict["ane_W"] = cpu_metrics.get("ane_energy", 0) / 1000
    cpu_metric_dict["cpu_W"] = cpu_metrics.get("cpu_energy", 0) / 1000
    cpu_metric_dict["gpu_W"] = cpu_metrics.get("gpu_energy", 0) / 1000
    cpu_metric_dict["package_W"] = cpu_metrics.get("combined_power", 0) / 1000

    return cpu_metric_dict


def parse_gpu_metrics(powermetrics_parse):
    gpu_metrics = powermetrics_parse["gpu"]
    gpu_metrics_dict = {
        "freq_MHz": int(gpu_metrics["freq_hz"]),
        "active": _true_active_percent(gpu_metrics),
    }
    return gpu_metrics_dict