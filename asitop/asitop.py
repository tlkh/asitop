import os
from dashing import *
import psutil


def clear_console():
    command = 'clear'
    os.system(command)


def get_cpu_info():
    cpu_info = os.popen('sysctl -a | grep machdep.cpu').read()
    cpu_info_lines = cpu_info.split("\n")
    data_fields = ["machdep.cpu.brand_string", "machdep.cpu.core_count"]
    cpu_info_dict = {}
    for l in cpu_info_lines:
        for h in data_fields:
            if h in l:
                value = l.split(":")[1].strip()
                cpu_info_dict[h] = value
    return cpu_info_dict


def run_powermetrics():
    powermetrics = os.popen(
        'sudo powermetrics --samplers cpu_power,gpu_power,thermal,bandwidth -i1000 -n1').read()
    return powermetrics


def parse_cpu_metrics(cpu_metrics):
    cpu_metrics_lines = cpu_metrics.split("\n")
    cpu_metric_dict = {}
    power_headers = ["E-Cluster Power", "P-Cluster Power",
                     "P0-Cluster Power", "P1-Cluster Power", "Package Power",
                     "ANE Power", "DRAM Power"]
    for h in power_headers:
        for l in cpu_metrics_lines:
            if h in l:
                power_mw = int(l.split(":")[1].strip()[:-2])
                cpu_metric_dict[h] = power_mw
                break
    usage_headers = ["E-Cluster HW active residency", "P-Cluster HW active residency",
                     "P0-Cluster HW active residency", "P1-Cluster HW active residency"]
    for h in usage_headers:
        for l in cpu_metrics_lines:
            if h in l:
                l_split = l.split("%")[0]
                active_percent = float(l_split.split(":")[1].strip())
                cpu_metric_dict[h] = active_percent
                break
    freq_headers = ["E-Cluster HW active frequency", "P-Cluster HW active frequency",
                    "P0-Cluster HW active frequency", "P1-Cluster HW active frequency"]
    for h in freq_headers:
        for l in cpu_metrics_lines:
            if h in l:
                mhz = int(l.split(":")[1][:-3].strip())
                cpu_metric_dict[h] = mhz
                break
    if "P-Cluster Power" not in cpu_metric_dict:
        cpu_metric_dict["P-Cluster Power"] = cpu_metric_dict["P0-Cluster Power"] + \
            cpu_metric_dict["P1-Cluster Power"]
    if "P-Cluster HW active residency" not in cpu_metric_dict:
        cpu_metric_dict["P-Cluster HW active residency"] = (
            cpu_metric_dict["P0-Cluster HW active residency"] + cpu_metric_dict["P1-Cluster HW active residency"])/2
    if "P-Cluster HW active frequency" not in cpu_metric_dict:
        cpu_metric_dict["P-Cluster HW active frequency"] = max(
            cpu_metric_dict["P0-Cluster HW active frequency"], cpu_metric_dict["P1-Cluster HW active frequency"])
    return cpu_metric_dict


def parse_gpu_metrics(gpu_metrics):
    gpu_metrics_lines = gpu_metrics.split("\n")
    gpu_metrics_dict = {}
    data_fields = ["GPU active residency", "GPU Power", "GPU active frequency"]
    for h in data_fields:
        for l in gpu_metrics_lines:
            if h in l:
                l_split = l.split(":")
                header, value = l_split[0], l_split[1]
                if "Power" in header:
                    value = int(value.split("mW")[0].strip())
                elif "residency" in header:
                    value = float(value.split("%")[0].strip())
                elif "frequency" in header:
                    value = int(value.split("MHz")[0].strip())
                gpu_metrics_dict[h] = value
                break
    return gpu_metrics_dict


def parse_thermal_pressure(thermal_pressure):
    thermal_pressure = thermal_pressure.replace("\n", "").strip()
    _, pressure = thermal_pressure.split(":")
    return pressure.strip()


def parse_bandwidth_metrics(bandwidth_metrics):
    bandwidth_metrics_lines = bandwidth_metrics.split("\n")
    bandwidth_metrics_dict = {}
    data_fields = ["PCPU0 RD", "PCPU0 WR",
                   "PCPU1 RD", "PCPU1 WR",
                   "PCPU RD", "PCPU WR",
                   "ECPU RD", "ECPU WR",
                   "GFX RD", "GFX WR"]
    for h in data_fields:
        for l in bandwidth_metrics_lines:
            if h in l:
                value = l.split(":")[1]
                value = float(value.split("MB/s")[0].strip())
                bandwidth_metrics_dict[h] = value
                break
    if "PCPU RD" not in bandwidth_metrics_dict:
        bandwidth_metrics_dict["PCPU RD"] = bandwidth_metrics_dict["PCPU0 RD"] + \
            bandwidth_metrics_dict["PCPU1 RD"]
    if "PCPU WR" not in bandwidth_metrics_dict:
        bandwidth_metrics_dict["PCPU WR"] = bandwidth_metrics_dict["PCPU0 WR"] + \
            bandwidth_metrics_dict["PCPU1 WR"]
    return bandwidth_metrics_dict


def parse_powermetrics(powermetrics):
    _, cpu_gpu_metrics = powermetrics.split("**** Processor usage ****")
    cpu_metrics, thermal_gpu_bandwidth_metrics = cpu_gpu_metrics.split(
        "**** Thermal pressure ****")
    thermal_pressure, gpu_bandwidth_metrics = thermal_gpu_bandwidth_metrics.split(
        "**** GPU usage ****")
    gpu_metrics, bandwidth_metrics = gpu_bandwidth_metrics.split(
        "**** Bandwidth Counters ****")
    thermal_pressure = parse_thermal_pressure(thermal_pressure)
    cpu_metrics_dict = parse_cpu_metrics(cpu_metrics)
    gpu_metrics_dict = parse_gpu_metrics(gpu_metrics)
    bandwidth_metrics = parse_bandwidth_metrics(bandwidth_metrics)
    return cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, bandwidth_metrics


def convert_to_GB(value):
    return round(value/1024/1024/1024, 1)


def get_ram_metrics_dict():
    ram_metrics = psutil.virtual_memory()
    swap_metrics = psutil.swap_memory()
    total_GB = convert_to_GB(ram_metrics.total)
    free_GB = convert_to_GB(ram_metrics.available)
    used_GB = convert_to_GB(ram_metrics.total-ram_metrics.available)
    swap_total_GB = convert_to_GB(swap_metrics.total)
    swap_used_GB = convert_to_GB(swap_metrics.used)
    swap_free_GB = convert_to_GB(swap_metrics.total-swap_metrics.used)
    ram_metrics_dict = {
        "total_GB": round(total_GB, 1),
        "free_GB": round(free_GB, 1),
        "used_GB": round(used_GB, 1),
        "free_percent": int(100-(ram_metrics.available/ram_metrics.total*100)),
        "swap_total_GB": swap_total_GB,
        "swap_used_GB": swap_used_GB,
        "swap_free_GB": swap_free_GB,
        "swap_free_percent": int(100-(swap_free_GB/swap_total_GB*100)),
    }
    return ram_metrics_dict


def main():
    print("\n[1/2] Loading ASITOP\n")

    ui = VSplit(
        VSplit(
            HSplit(
                HGauge(title="E-CPU Usage", val=0, color=2),
                HGauge(title="P-CPU Usage", val=0, color=2),
            ),
            HGauge(title="GPU Usage", val=0, color=2),

            title="Usage Gauge",
            border_color=2,
        ),
        VSplit(
            HGauge(title="RAM Usage", val=0, color=2),
            HSplit(
                HGauge(title="E-CPU B/W", val=50, color=2),
                HGauge(title="P-CPU B/W", val=50, color=2),
                HGauge(title="GPU B/W", val=50, color=2),
            ),
            border_color=2,
            title="Memory"
        ),
        HSplit(
            HChart(title="CPU Power", color=2),
            HChart(title="GPU Power", color=2),
            title="Power Chart",
            border_color=2,
        ),
    )

    usage_gauges = ui.items[0]
    memory_gauges = ui.items[1]
    power_charts = ui.items[2]

    cpu_gauges = usage_gauges.items[0]
    cpu1_gauge = cpu_gauges.items[0]
    cpu2_gauge = cpu_gauges.items[1]
    gpu_gauge = usage_gauges.items[1]

    ram_gauge = memory_gauges.items[0]

    bw_gauges = memory_gauges.items[1]
    ecpu_bw_gauge = bw_gauges.items[0]
    pcpu_bw_gauge = bw_gauges.items[1]
    gpu_bw_gauge = bw_gauges.items[2]

    cpu_power_chart = power_charts.items[0]
    gpu_power_chart = power_charts.items[1]

    cpu_info_dict = get_cpu_info()
    cpu_title = cpu_info_dict["machdep.cpu.brand_string"] + \
        " (" + cpu_info_dict["machdep.cpu.core_count"] + "-core)"
    if cpu_info_dict["machdep.cpu.brand_string"] == "Apple M1 Max" or cpu_info_dict["machdep.cpu.brand_string"] == "Apple M1 Pro":
        cpu_max_power = 35
        gpu_max_power = 65
    elif cpu_info_dict["machdep.cpu.brand_string"] == "Apple M1":
        cpu_max_power = 25
        gpu_max_power = 20
    if cpu_info_dict["machdep.cpu.brand_string"] == "Apple M1 Max":
        max_cpu_bw = 200
        max_gpu_bw = 200
    elif cpu_info_dict["machdep.cpu.brand_string"] == "Apple M1 Pro":
        max_cpu_bw = 200
        max_gpu_bw = 200
    elif cpu_info_dict["machdep.cpu.brand_string"] == "Apple M1":
        max_cpu_bw = 70
        max_gpu_bw = 70

    cpu_peak_power = 0
    gpu_peak_power = 0
    package_peak_power = 0

    print("\n[2/2] ASITOP: Taking first measurement\n")

    powermetrics = run_powermetrics()

    clear_console()

    while True:
        try:
            cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, bandwidth_metrics = parse_powermetrics(
                powermetrics)

            if thermal_pressure == "Nominal":
                thermal_throttle = "no"
            else:
                thermal_throttle = "yes"

            usage_gauges.title = cpu_title

            cpu1_freq = str(
                cpu_metrics_dict["E-Cluster HW active frequency"])+"MHz"
            cpu2_freq = str(
                cpu_metrics_dict["P-Cluster HW active frequency"])+"MHz"
            gpu_freq = str(gpu_metrics_dict["GPU active frequency"])+"MHz"

            cpu1_gauge.title = "E-CPU Usage: " + \
                str(round(
                    cpu_metrics_dict["E-Cluster HW active residency"], 1))+"% @ "+cpu1_freq
            cpu1_gauge.value = int(
                cpu_metrics_dict["E-Cluster HW active residency"])
            cpu2_gauge.title = "P-CPU Usage: " + \
                str(round(
                    cpu_metrics_dict["P-Cluster HW active residency"], 1))+"% @ "+cpu2_freq
            cpu2_gauge.value = int(
                cpu_metrics_dict["P-Cluster HW active residency"])
            gpu_gauge.title = "GPU Usage: " + \
                str(round(
                    gpu_metrics_dict["GPU active residency"], 1))+"% @ "+gpu_freq
            gpu_gauge.value = int(gpu_metrics_dict["GPU active residency"])

            ram_metrics_dict = get_ram_metrics_dict()
            ram_gauge.title = "RAM Usage: " + \
                str(ram_metrics_dict["used_GB"])+"GB/" + \
                str(ram_metrics_dict["total_GB"])+"GB" + \
                " swap: " + \
                str(ram_metrics_dict["swap_used_GB"])+"GB/" + \
                str(ram_metrics_dict["swap_total_GB"])+"GB"
            ram_gauge.value = int(ram_metrics_dict["free_percent"])

            ecpu_bw_percent = int(
                (bandwidth_metrics["ECPU RD"]+bandwidth_metrics["ECPU WR"])/1000/max_cpu_bw*100)
            ecpu_read_GB = round(bandwidth_metrics["ECPU RD"]/1000, 1)
            ecpu_write_GB = round(bandwidth_metrics["ECPU WR"]/1000, 1)
            ecpu_bw_gauge.title = "E-CPU R:" + \
                str(ecpu_read_GB)+" W:"+str(ecpu_write_GB)
            ecpu_bw_gauge.value = ecpu_bw_percent

            pcpu_bw_percent = int(
                (bandwidth_metrics["PCPU RD"]+bandwidth_metrics["PCPU WR"])/1000/max_cpu_bw*100)
            pcpu_read_GB = round(bandwidth_metrics["PCPU RD"]/1000, 1)
            pcpu_write_GB = round(bandwidth_metrics["PCPU WR"]/1000, 1)
            pcpu_bw_gauge.title = "P-CPU R:" + \
                str(pcpu_read_GB)+" W:"+str(pcpu_write_GB)
            pcpu_bw_gauge.value = pcpu_bw_percent

            gpu_bw_percent = int(
                (bandwidth_metrics["GFX RD"]+bandwidth_metrics["GFX WR"])/1000/max_gpu_bw*100)
            gpu_read_GB = round(bandwidth_metrics["GFX RD"]/1000, 1)
            gpu_write_GB = round(bandwidth_metrics["GFX WR"]/1000, 1)
            gpu_bw_gauge.title = "GPU R:" + \
                str(gpu_read_GB)+" W:"+str(gpu_write_GB)
            gpu_bw_gauge.value = gpu_bw_percent

            total_bw_GB = round(
                ecpu_read_GB+ecpu_write_GB+pcpu_read_GB+pcpu_write_GB+gpu_read_GB+gpu_write_GB, 1)
            bw_gauges.title = "Memory Bandwidth (GB/s) - total: " + \
                str(total_bw_GB)+" GB/s"

            package_power_W = cpu_metrics_dict["Package Power"]/1000
            if package_power_W > package_peak_power:
                package_peak_power = package_power_W
            power_charts.title = "Package Power: "+str(round(package_power_W, 1))+"W - peak: "+str(
                round(package_peak_power, 1))+"W - throttle: "+str(thermal_throttle)
            cpu_power_percent = int(
                (cpu_metrics_dict["E-Cluster Power"]+cpu_metrics_dict["P-Cluster Power"])/1000/cpu_max_power*100)
            cpu_power_W = (
                cpu_metrics_dict["E-Cluster Power"]+cpu_metrics_dict["P-Cluster Power"])/1000
            if cpu_power_W > cpu_peak_power:
                cpu_peak_power = cpu_power_W
            cpu_power_chart.title = "CPU Power: " + \
                str(round(cpu_power_W, 1))+"W - peak: " + \
                str(round(cpu_peak_power, 1))+"W"
            cpu_power_chart.append(cpu_power_percent)
            gpu_power_percent = int(
                gpu_metrics_dict["GPU Power"]/1000/gpu_max_power*100)
            gpu_power_W = gpu_metrics_dict["GPU Power"]/1000
            if gpu_power_W > gpu_peak_power:
                gpu_peak_power = gpu_power_W
            gpu_power_chart.title = "GPU Power: " + \
                str(round(gpu_power_W, 1))+"W - peak: " + \
                str(round(gpu_peak_power, 1))+"W"
            gpu_power_chart.append(gpu_power_percent)

            ui.display()

            powermetrics = run_powermetrics()
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
