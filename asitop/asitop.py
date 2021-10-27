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
        'sudo powermetrics --samplers cpu_power,gpu_power,thermal -i1000 -n1').read()
    return powermetrics


def parse_cpu_metrics(cpu_metrics):
    cpu_metrics_lines = cpu_metrics.split("\n")
    cpu_metric_dict = {}
    power_headers = ["E-Cluster Power", "P-Cluster Power",
                     "P0-Cluster Power", "P1-Cluster Power", "Package Power"]
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


def parse_powermetrics(powermetrics):
    _, cpu_gpu_metrics = powermetrics.split("**** Processor usage ****")
    cpu_metrics, thermal_gpu_metrics = cpu_gpu_metrics.split(
        "**** Thermal pressure ****")
    thermal_pressure, gpu_metrics = thermal_gpu_metrics.split(
        "**** GPU usage ****")
    thermal_pressure = parse_thermal_pressure(thermal_pressure)
    cpu_metrics_dict = parse_cpu_metrics(cpu_metrics)
    gpu_metrics_dict = parse_gpu_metrics(gpu_metrics)
    return cpu_metrics_dict, gpu_metrics_dict, thermal_pressure


def convert_to_GB(value):
    return value/1024/1024/1024


def get_ram_metrics_dict():
    ram_metrics = psutil.virtual_memory()
    total_GB = convert_to_GB(ram_metrics.total)
    free_GB = convert_to_GB(ram_metrics.available)
    used_GB = convert_to_GB(ram_metrics.total-ram_metrics.available)
    ram_metrics_dict = {
        "total_GB": round(total_GB, 1),
        "free_GB": round(free_GB, 1),
        "used_GB": round(used_GB, 1),
        "free_percent": 100.0-round(ram_metrics.available/ram_metrics.total*100, 1)
    }
    return ram_metrics_dict


def main():
    print("\n[1/2] Loading ASITOP\n")

    ui = VSplit(
        VSplit(
            HGauge(title="E-CPU Usage", val=0, color=2),
            HGauge(title="P-CPU Usage", val=0, color=2),
            HGauge(title="GPU Usage", val=0, color=2),
            HGauge(title="RAM Usage", val=0, color=2),
            title="Usage Gauge",
            border_color=2,
        ),
        VSplit(
            HChart(title="CPU Power", color=2),
            HChart(title="GPU Power", color=2),
            title="Power Chart",
            border_color=2,
        ),
    )

    usage_gauges = ui.items[0]
    power_charts = ui.items[1]

    cpu1_gauge = usage_gauges.items[0]
    cpu2_gauge = usage_gauges.items[1]
    gpu_gauge = usage_gauges.items[2]
    ram_gauge = usage_gauges.items[3]

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

    cpu_peak_power = 0
    gpu_peak_power = 0
    package_peak_power = 0

    run = True

    print("\n[2/2] ASITOP: Taking first measurement\n")

    powermetrics = run_powermetrics()

    clear_console()

    while run:
        try:
            cpu_metrics_dict, gpu_metrics_dict, thermal_pressure = parse_powermetrics(
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

            cpu_active = (+cpu_metrics_dict["P-Cluster HW active residency"])/2
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
                str(ram_metrics_dict["total_GB"])+"GB"
            ram_gauge.value = int(ram_metrics_dict["free_percent"])

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
