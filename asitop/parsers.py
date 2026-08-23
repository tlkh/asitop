import math


def parse_thermal_pressure(powermetrics_parse):
    return powermetrics_parse["thermal_pressure"]


def parse_bandwidth_metrics(powermetrics_parse):
    bandwidth_metrics = powermetrics_parse["bandwidth_counters"]
    bandwidth_metrics_dict = {}
    data_fields = ["PCPU0 DCS RD", "PCPU0 DCS WR",
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
                   "DCS RD", "DCS WR"]
    for h in data_fields:
        bandwidth_metrics_dict[h] = 0
    for l in bandwidth_metrics:
        if l["name"] in data_fields:
            bandwidth_metrics_dict[l["name"]] = l["value"]/(1e9)
    bandwidth_metrics_dict["PCPU DCS RD"] = bandwidth_metrics_dict["PCPU DCS RD"] + \
        bandwidth_metrics_dict["PCPU0 DCS RD"] + \
        bandwidth_metrics_dict["PCPU1 DCS RD"] + \
        bandwidth_metrics_dict["PCPU2 DCS RD"] + \
        bandwidth_metrics_dict["PCPU3 DCS RD"]
    bandwidth_metrics_dict["PCPU DCS WR"] = bandwidth_metrics_dict["PCPU DCS WR"] + \
        bandwidth_metrics_dict["PCPU0 DCS WR"] + \
        bandwidth_metrics_dict["PCPU1 DCS WR"] + \
        bandwidth_metrics_dict["PCPU2 DCS WR"] + \
        bandwidth_metrics_dict["PCPU3 DCS WR"]
    bandwidth_metrics_dict["JPG DCS RD"] = bandwidth_metrics_dict["JPG DCS RD"] + \
        bandwidth_metrics_dict["JPG0 DCS RD"] + \
        bandwidth_metrics_dict["JPG1 DCS RD"] + \
        bandwidth_metrics_dict["JPG2 DCS RD"] + \
        bandwidth_metrics_dict["JPG3 DCS RD"]
    bandwidth_metrics_dict["JPG DCS WR"] = bandwidth_metrics_dict["JPG DCS WR"] + \
        bandwidth_metrics_dict["JPG0 DCS WR"] + \
        bandwidth_metrics_dict["JPG1 DCS WR"] + \
        bandwidth_metrics_dict["JPG2 DCS WR"] + \
        bandwidth_metrics_dict["JPG3 DCS WR"]
    bandwidth_metrics_dict["VENC DCS RD"] = bandwidth_metrics_dict["VENC DCS RD"] + \
        bandwidth_metrics_dict["VENC0 DCS RD"] + \
        bandwidth_metrics_dict["VENC1 DCS RD"] + \
        bandwidth_metrics_dict["VENC2 DCS RD"] + \
        bandwidth_metrics_dict["VENC3 DCS RD"]
    bandwidth_metrics_dict["VENC DCS WR"] = bandwidth_metrics_dict["VENC DCS WR"] + \
        bandwidth_metrics_dict["VENC0 DCS WR"] + \
        bandwidth_metrics_dict["VENC1 DCS WR"] + \
        bandwidth_metrics_dict["VENC2 DCS WR"] + \
        bandwidth_metrics_dict["VENC3 DCS WR"]
    bandwidth_metrics_dict["MEDIA DCS"] = sum([
        bandwidth_metrics_dict["ISP DCS RD"], bandwidth_metrics_dict["ISP DCS WR"],
        bandwidth_metrics_dict["STRM CODEC DCS RD"], bandwidth_metrics_dict["STRM CODEC DCS WR"],
        bandwidth_metrics_dict["PRORES DCS RD"], bandwidth_metrics_dict["PRORES DCS WR"],
        bandwidth_metrics_dict["VDEC DCS RD"], bandwidth_metrics_dict["VDEC DCS WR"],
        bandwidth_metrics_dict["VENC DCS RD"], bandwidth_metrics_dict["VENC DCS WR"],
        bandwidth_metrics_dict["JPG DCS RD"], bandwidth_metrics_dict["JPG DCS WR"],
    ])
    return bandwidth_metrics_dict


def _finite_float(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _active_percent(metrics):
    if "active_ratio" in metrics:
        active_ratio = _finite_float(metrics["active_ratio"])
    else:
        idle_ratio = _finite_float(metrics.get("idle_ratio"), 1.0)
        down_ratio = _finite_float(metrics.get("down_ratio"))
        active_ratio = 1 - idle_ratio - down_ratio
    return round(max(0, min(100, active_ratio * 100)))


def _frequency_mhz(metrics):
    return int(max(0, _finite_float(metrics.get("freq_hz"))) / 1e6)


def _cluster_family(cluster_name):
    normalized_name = str(cluster_name).strip().upper()
    normalized_name = normalized_name.replace("_", "-").replace(" ", "-")
    if "EFFICIENCY" in normalized_name:
        return "E"
    if "PERFORMANCE" in normalized_name:
        return "P"
    if "SUPER" in normalized_name:
        return "S"

    cluster_prefix = normalized_name.split("-CLUSTER", 1)[0]
    cluster_prefix = cluster_prefix.rstrip("0123456789").strip(" -_")
    return cluster_prefix or "CPU"


def _average(values):
    return round(sum(values) / len(values)) if values else 0


def parse_cpu_metrics(powermetrics_parse):
    cpu_metrics = powermetrics_parse["processor"]
    cpu_metric_dict = {}
    group_map = {}

    for cluster in cpu_metrics.get("clusters", []):
        cluster_name = cluster["name"]
        family = _cluster_family(cluster_name)
        cluster_active = _active_percent(cluster)
        cluster_frequency = _frequency_mhz(cluster)
        cores = []

        cpu_metric_dict[cluster_name + "_active"] = cluster_active
        cpu_metric_dict[cluster_name + "_freq_Mhz"] = cluster_frequency

        group = group_map.setdefault(family, {
            "family": family,
            "label": family + "-CPU",
            "clusters": [],
            "cores": [],
        })

        for cpu in cluster.get("cpus", []):
            core = {
                "id": cpu["cpu"],
                "active": _active_percent(cpu),
                "freq_Mhz": _frequency_mhz(cpu),
            }
            cores.append(core)
            group["cores"].append(core)
            legacy_prefix = family + "-Cluster" + str(core["id"])
            cpu_metric_dict[legacy_prefix + "_active"] = core["active"]
            cpu_metric_dict[legacy_prefix + "_freq_Mhz"] = core["freq_Mhz"]

        group["clusters"].append({
            "name": cluster_name,
            "active": cluster_active,
            "freq_Mhz": cluster_frequency,
            "cores": cores,
        })

    cluster_groups = []
    for group in group_map.values():
        core_activity = [core["active"] for core in group["cores"]]
        cluster_activity = [cluster["active"] for cluster in group["clusters"]]
        cluster_frequencies = [
            cluster["freq_Mhz"] for cluster in group["clusters"]
        ]
        group["active"] = _average(core_activity or cluster_activity)
        group["freq_Mhz"] = max(cluster_frequencies, default=0)
        group["core_count"] = len(group["cores"])
        cluster_groups.append(group)

        family_prefix = group["family"] + "-Cluster"
        cpu_metric_dict[family_prefix + "_active"] = group["active"]
        cpu_metric_dict[family_prefix + "_freq_Mhz"] = group["freq_Mhz"]

    cpu_metric_dict["cluster_groups"] = cluster_groups
    cpu_metric_dict["e_core"] = [
        core["id"] for core in group_map.get("E", {}).get("cores", [])
    ]
    cpu_metric_dict["p_core"] = [
        core["id"] for core in group_map.get("P", {}).get("cores", [])
    ]

    for family in ("E", "P"):
        family_prefix = family + "-Cluster"
        cpu_metric_dict.setdefault(family_prefix + "_active", 0)
        cpu_metric_dict.setdefault(family_prefix + "_freq_Mhz", 0)

    cpu_metric_dict["ane_W"] = cpu_metrics.get("ane_energy", 0) / 1000
    cpu_metric_dict["cpu_W"] = cpu_metrics.get("cpu_energy", 0) / 1000
    cpu_metric_dict["gpu_W"] = cpu_metrics.get("gpu_energy", 0) / 1000
    combined_power = cpu_metrics.get(
        "combined_power",
        cpu_metrics.get("ane_energy", 0)
        + cpu_metrics.get("cpu_energy", 0)
        + cpu_metrics.get("gpu_energy", 0),
    )
    cpu_metric_dict["package_W"] = combined_power / 1000
    return cpu_metric_dict


def parse_gpu_metrics(powermetrics_parse):
    gpu_metrics = powermetrics_parse["gpu"]
    gpu_metrics_dict = {
        "freq_MHz": round(max(0, _finite_float(gpu_metrics.get("freq_hz")))),
        "active": _active_percent(gpu_metrics),
    }
    return gpu_metrics_dict
