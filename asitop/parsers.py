def parse_thermal_pressure(powermetrics_parse):
    return powermetrics_parse["thermal_pressure"]


def parse_bandwidth_metrics(powermetrics_parse):
    bandwidth_metrics = powermetrics_parse["bandwidth_counters"]
    bandwidth_metrics_dict = {}
    data_fields = ["PCPU0 DCS RD", "PCPU0 DCS WR",
                   "PCPU1 DCS RD", "PCPU1 DCS WR",
                   "PCPU DCS RD", "PCPU DCS WR",
                   "ECPU DCS RD", "ECPU DCS WR",
                   "GFX DCS RD", "GFX DCS WR",
                   "DCS RD", "DCS WR"]
    for l in bandwidth_metrics:
        if l["name"] in data_fields:
            bandwidth_metrics_dict[l["name"]] = l["value"]/(1e9)
    if "PCPU DCS RD" not in bandwidth_metrics_dict:
        bandwidth_metrics_dict["PCPU DCS RD"] = bandwidth_metrics_dict["PCPU0 DCS RD"] + \
            bandwidth_metrics_dict["PCPU1 DCS RD"]
    if "PCPU DCS WR" not in bandwidth_metrics_dict:
        bandwidth_metrics_dict["PCPU DCS WR"] = bandwidth_metrics_dict["PCPU0 DCS WR"] + \
            bandwidth_metrics_dict["PCPU1 DCS WR"]
    return bandwidth_metrics_dict


def parse_cpu_metrics(powermetrics_parse):
    cpu_metrics = powermetrics_parse["processor"]
    cpu_metric_dict = {}
    # cpu_clusters
    cpu_clusters = cpu_metrics["clusters"]
    for cluster in cpu_clusters:
        name = cluster["name"]
        cpu_metric_dict[name+"_freq_Mhz"] = int(cluster["freq_hz"]/(1e6))
        cpu_metric_dict[name+"_active"] = int((1 - cluster["idle_ratio"])*100)
    if "P-Cluster_active" not in cpu_metric_dict:
        cpu_metric_dict["P-Cluster_active"] = int((
            cpu_metric_dict["P0-Cluster_active"] + cpu_metric_dict["P1-Cluster_active"])/2)
    if "P-Cluster_freq_Mhz" not in cpu_metric_dict:
        cpu_metric_dict["P-Cluster_freq_Mhz"] = max(
            cpu_metric_dict["P0-Cluster_freq_Mhz"], cpu_metric_dict["P1-Cluster_freq_Mhz"])
    # power
    cpu_metric_dict["ane_W"] = cpu_metrics["ane_energy"]/1000
    cpu_metric_dict["dram_W"] = cpu_metrics["dram_energy"]/1000
    cpu_metric_dict["cpu_W"] = cpu_metrics["cpu_energy"]/1000
    cpu_metric_dict["gpu_W"] = cpu_metrics["gpu_energy"]/1000
    cpu_metric_dict["package_W"] = cpu_metrics["package_energy"]/1000
    return cpu_metric_dict


def parse_gpu_metrics(powermetrics_parse):
    gpu_metrics = powermetrics_parse["gpu"]
    gpu_metrics_dict = {
        "freq_MHz": int(gpu_metrics["freq_hz"]),
        "active": int((1 - gpu_metrics["idle_ratio"])*100),
    }
    return gpu_metrics_dict
