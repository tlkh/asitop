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
                   "ISP DCS RD", "ISP DCS WR",
                   "STRM CODEC DCS RD", "STRM CODEC DCS WR",
                   "PRORES DCS RD", "PRORES DCS WR",
                   "VDEC DCS RD", "VDEC DCS WR",
                   "VENC0 DCS RD", "VENC0 DCS WR",
                   "VENC1 DCS RD", "VENC1 DCS WR",
                   "VENC DCS RD", "VENC DCS WR",
                   "JPG0 DCS RD", "JPG0 DCS WR",
                   "JPG1 DCS RD", "JPG1 DCS WR",
                   "JPG DCS RD", "JPG DCS WR",
                   "DCS RD", "DCS WR"]
    for h in data_fields:
        bandwidth_metrics_dict[h] = 0
    for l in bandwidth_metrics:
        if l["name"] in data_fields:
            bandwidth_metrics_dict[l["name"]] = l["value"]/(1e9)
    bandwidth_metrics_dict["PCPU DCS RD"] = bandwidth_metrics_dict["PCPU DCS RD"] + \
        bandwidth_metrics_dict["PCPU0 DCS RD"] + \
        bandwidth_metrics_dict["PCPU1 DCS RD"]
    bandwidth_metrics_dict["PCPU DCS WR"] = bandwidth_metrics_dict["PCPU DCS WR"] + \
        bandwidth_metrics_dict["PCPU0 DCS WR"] + \
        bandwidth_metrics_dict["PCPU1 DCS WR"]
    bandwidth_metrics_dict["JPG DCS RD"] = bandwidth_metrics_dict["JPG DCS RD"] + \
        bandwidth_metrics_dict["JPG0 DCS RD"] + \
        bandwidth_metrics_dict["JPG1 DCS RD"]
    bandwidth_metrics_dict["JPG DCS WR"] = bandwidth_metrics_dict["JPG DCS WR"] + \
        bandwidth_metrics_dict["JPG0 DCS WR"] + \
        bandwidth_metrics_dict["JPG1 DCS WR"]
    bandwidth_metrics_dict["VENC DCS RD"] = bandwidth_metrics_dict["VENC DCS RD"] + \
        bandwidth_metrics_dict["VENC0 DCS RD"] + \
        bandwidth_metrics_dict["VENC1 DCS RD"]
    bandwidth_metrics_dict["VENC DCS WR"] = bandwidth_metrics_dict["VENC DCS WR"] + \
        bandwidth_metrics_dict["VENC0 DCS WR"] + \
        bandwidth_metrics_dict["VENC1 DCS WR"]
    bandwidth_metrics_dict["MEDIA DCS"] = sum([
        bandwidth_metrics_dict["ISP DCS RD"], bandwidth_metrics_dict["ISP DCS WR"],
        bandwidth_metrics_dict["STRM CODEC DCS RD"], bandwidth_metrics_dict["STRM CODEC DCS WR"],
        bandwidth_metrics_dict["PRORES DCS RD"], bandwidth_metrics_dict["PRORES DCS WR"],
        bandwidth_metrics_dict["VDEC DCS RD"], bandwidth_metrics_dict["VDEC DCS WR"],
        bandwidth_metrics_dict["VENC DCS RD"], bandwidth_metrics_dict["VENC DCS WR"],
        bandwidth_metrics_dict["JPG DCS RD"], bandwidth_metrics_dict["JPG DCS WR"],
    ])
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
