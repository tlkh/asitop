
import time
import argparse
from collections import deque
from dashing import VSplit, HSplit, HGauge, HChart
from .utils import *


parser = argparse.ArgumentParser(
    description='asitop: Performance monitoring CLI tool for Apple Silicon')
parser.add_argument('--interval', type=int, default=1,
                    help='Display interval and sampling interval for powermetrics (seconds)')
parser.add_argument('--color', type=int, default=2,
                    help='Choose display color (0~8)')
parser.add_argument('--avg', type=int, default=30,
                    help='Interval for averaged values (seconds)')
args = parser.parse_args()


def main():
    print("\nASITOP - Performance monitoring CLI tool for Apple Silicon")
    print("You can update ASITOP by running `pip install asitop --upgrade`")
    print("Get help at `https://github.com/tlkh/asitop`")
    print("P.S. You are recommended to run ASITOP with `sudo asitop`\n")
    print("\n[1/3] Loading ASITOP\n")

    ui = VSplit(
        VSplit(
            HSplit(
                HGauge(title="E-CPU Usage", val=0, color=args.color),
                HGauge(title="P-CPU Usage", val=0, color=args.color),
            ),
            HSplit(
                HGauge(title="GPU Usage", val=0, color=args.color),
                HGauge(title="ANE", val=0, color=args.color),
            ),
            title="Processor Utilization",
            border_color=args.color,
        ),
        VSplit(
            HGauge(title="RAM Usage", val=0, color=args.color),
            HSplit(
                HGauge(title="E-CPU B/W", val=50, color=args.color),
                HGauge(title="P-CPU B/W", val=50, color=args.color),
                HGauge(title="GPU B/W", val=50, color=args.color),
                HGauge(title="Media B/W", val=50, color=args.color),
            ),
            border_color=args.color,
            title="Memory"
        ),
        HSplit(
            HChart(title="CPU Power", color=args.color),
            HChart(title="GPU Power", color=args.color),
            title="Power Chart",
            border_color=args.color,
        ),
    )

    usage_gauges = ui.items[0]
    memory_gauges = ui.items[1]
    power_charts = ui.items[2]

    cpu_gauges = usage_gauges.items[0]
    cpu1_gauge = cpu_gauges.items[0]
    cpu2_gauge = cpu_gauges.items[1]
    acc_gauges = usage_gauges.items[1]
    gpu_gauge = acc_gauges.items[0]
    ane_gauge = acc_gauges.items[1]

    ram_gauge = memory_gauges.items[0]

    bw_gauges = memory_gauges.items[1]
    ecpu_bw_gauge = bw_gauges.items[0]
    pcpu_bw_gauge = bw_gauges.items[1]
    gpu_bw_gauge = bw_gauges.items[2]
    media_bw_gauge = bw_gauges.items[3]

    cpu_power_chart = power_charts.items[0]
    gpu_power_chart = power_charts.items[1]

    soc_info_dict = get_soc_info()

    cpu_title = "".join([
        soc_info_dict["name"],
        " (cores: ",
        str(soc_info_dict["e_core_count"]),
        "E+",
        str(soc_info_dict["p_core_count"]),
        "P+",
        str(soc_info_dict["gpu_core_count"]),
        "GPU)"
    ])
    usage_gauges.title = cpu_title
    cpu_max_power = soc_info_dict["cpu_max_power"]
    gpu_max_power = soc_info_dict["gpu_max_power"]
    ane_max_power = 8.0
    max_cpu_bw = soc_info_dict["cpu_max_bw"]
    max_gpu_bw = soc_info_dict["gpu_max_bw"]
    max_media_bw = 7.0

    cpu_peak_power = 0
    gpu_peak_power = 0
    package_peak_power = 0

    print("\n[2/3] Starting powermetrics process\n")

    timecode = str(int(time.time()))

    powermetrics_process = run_powermetrics_process(timecode,
                                                    interval=args.interval*1000)

    print("\n[3/3] Waiting for first reading...\n")

    def get_reading(wait=0.1):
        ready = parse_powermetrics(timecode=timecode)
        while not ready:
            time.sleep(wait)
            ready = parse_powermetrics(timecode=timecode)
        return ready

    ready = get_reading()
    last_timestamp = ready[-1]

    def get_avg(inlist):
        avg = sum(inlist)/len(inlist)
        return avg

    avg_package_power_list = deque([], maxlen=int(args.avg/args.interval))
    avg_cpu_power_list = deque([], maxlen=int(args.avg/args.interval))
    avg_gpu_power_list = deque([], maxlen=int(args.avg/args.interval))

    clear_console()

    try:
        while True:
            ready = parse_powermetrics(timecode=timecode)
            if ready:
                cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, bandwidth_metrics, timestamp = ready

                if timestamp > last_timestamp:
                    last_timestamp = timestamp

                    if thermal_pressure == "Nominal":
                        thermal_throttle = "no"
                    else:
                        thermal_throttle = "yes"

                    cpu1_gauge.title = "".join([
                        "E-CPU Usage: ",
                        str(cpu_metrics_dict["E-Cluster_active"]),
                        "% @ ",
                        str(cpu_metrics_dict["E-Cluster_freq_Mhz"]),
                        " MHz"
                    ])
                    cpu1_gauge.value = cpu_metrics_dict["E-Cluster_active"]

                    cpu2_gauge.title = "".join([
                        "P-CPU Usage: ",
                        str(cpu_metrics_dict["P-Cluster_active"]),
                        "% @ ",
                        str(cpu_metrics_dict["P-Cluster_freq_Mhz"]),
                        " MHz"
                    ])
                    cpu2_gauge.value = cpu_metrics_dict["P-Cluster_active"]

                    gpu_gauge.title = "".join([
                        "GPU Usage: ",
                        str(gpu_metrics_dict["active"]),
                        "% @ ",
                        str(gpu_metrics_dict["freq_MHz"]),
                        " MHz"
                    ])
                    gpu_gauge.value = gpu_metrics_dict["active"]

                    ane_util_percent = int(
                        cpu_metrics_dict["ane_W"]/args.interval/ane_max_power*100)
                    ane_gauge.title = "".join([
                        "ANE Usage: ",
                        str(ane_util_percent),
                        "% @ ",
                        '{0:.1f}'.format(
                            cpu_metrics_dict["ane_W"]/args.interval),
                        " W"
                    ])
                    ane_gauge.value = ane_util_percent

                    ram_metrics_dict = get_ram_metrics_dict()

                    if ram_metrics_dict["swap_total_GB"] < 0.1:
                        ram_gauge.title = "".join([
                            "RAM Usage: ",
                            str(ram_metrics_dict["used_GB"]),
                            "/",
                            str(ram_metrics_dict["total_GB"]),
                            "GB - swap inactive"
                        ])
                    else:
                        ram_gauge.title = "".join([
                            "RAM Usage: ",
                            str(ram_metrics_dict["used_GB"]),
                            "/",
                            str(ram_metrics_dict["total_GB"]),
                            "GB",
                            " - swap:",
                            str(ram_metrics_dict["swap_used_GB"]),
                            "/",
                            str(ram_metrics_dict["swap_total_GB"]),
                            "GB"
                        ])
                    ram_gauge.value = ram_metrics_dict["free_percent"]

                    ecpu_bw_percent = int(
                        (bandwidth_metrics["ECPU DCS RD"]+bandwidth_metrics["ECPU DCS WR"])/args.interval/max_cpu_bw*100)
                    ecpu_read_GB = bandwidth_metrics["ECPU DCS RD"] / \
                        args.interval
                    ecpu_write_GB = bandwidth_metrics["ECPU DCS WR"] / \
                        args.interval
                    ecpu_bw_gauge.title = "".join([
                        "E-CPU: ",
                        '{0:.1f}'.format(ecpu_read_GB+ecpu_write_GB),
                        "GB/s"
                    ])
                    ecpu_bw_gauge.value = ecpu_bw_percent

                    pcpu_bw_percent = int(
                        (bandwidth_metrics["PCPU DCS RD"]+bandwidth_metrics["PCPU DCS WR"])/args.interval/max_cpu_bw*100)
                    pcpu_read_GB = bandwidth_metrics["PCPU DCS RD"] / \
                        args.interval
                    pcpu_write_GB = bandwidth_metrics["PCPU DCS WR"] / \
                        args.interval
                    pcpu_bw_gauge.title = "".join([
                        "P-CPU: ",
                        '{0:.1f}'.format(pcpu_read_GB+pcpu_write_GB),
                        "GB/s"
                    ])
                    pcpu_bw_gauge.value = pcpu_bw_percent

                    gpu_bw_percent = int(
                        (bandwidth_metrics["GFX DCS RD"]+bandwidth_metrics["GFX DCS WR"])/max_gpu_bw*100)
                    gpu_read_GB = bandwidth_metrics["GFX DCS RD"]
                    gpu_write_GB = bandwidth_metrics["GFX DCS WR"]
                    gpu_bw_gauge.title = "".join([
                        "GPU: ",
                        '{0:.1f}'.format(gpu_read_GB+gpu_write_GB),
                        "GB/s"
                    ])
                    gpu_bw_gauge.value = gpu_bw_percent

                    media_bw_percent = int(
                        bandwidth_metrics["MEDIA DCS"]/args.interval/max_media_bw*100)
                    media_bw_gauge.title = "".join([
                        "Media: ",
                        '{0:.1f}'.format(
                            bandwidth_metrics["MEDIA DCS"]/args.interval),
                        "GB/s"
                    ])
                    media_bw_gauge.value = media_bw_percent

                    total_bw_GB = (
                        bandwidth_metrics["DCS RD"] + bandwidth_metrics["DCS WR"])/args.interval
                    bw_gauges.title = "".join([
                        "Memory Bandwidth: ",
                        '{0:.2f}'.format(total_bw_GB),
                        " GB/s (R:",
                        '{0:.2f}'.format(
                            bandwidth_metrics["DCS RD"]/args.interval),
                        "/W:",
                        '{0:.2f}'.format(
                            bandwidth_metrics["DCS WR"]/args.interval),
                        " GB/s)"
                    ])

                    package_power_W = cpu_metrics_dict["package_W"] / \
                        args.interval
                    if package_power_W > package_peak_power:
                        package_peak_power = package_power_W
                    avg_package_power_list.append(package_power_W)
                    avg_package_power = get_avg(avg_package_power_list)
                    power_charts.title = "".join([
                        "Package Power: ",
                        '{0:.2f}'.format(package_power_W),
                        "W (avg: ",
                        '{0:.2f}'.format(avg_package_power),
                        "W peak: ",
                        '{0:.2f}'.format(package_peak_power),
                        "W) throttle: ",
                        thermal_throttle,
                    ])

                    cpu_power_percent = int(
                        cpu_metrics_dict["cpu_W"]/args.interval/cpu_max_power*100)
                    cpu_power_W = cpu_metrics_dict["cpu_W"]/args.interval
                    if cpu_power_W > cpu_peak_power:
                        cpu_peak_power = cpu_power_W
                    avg_cpu_power_list.append(cpu_power_W)
                    avg_cpu_power = get_avg(avg_cpu_power_list)
                    cpu_power_chart.title = "".join([
                        "CPU: ",
                        '{0:.2f}'.format(cpu_power_W),
                        "W (avg: ",
                        '{0:.2f}'.format(avg_cpu_power),
                        "W peak: ",
                        '{0:.2f}'.format(cpu_peak_power),
                        "W)"
                    ])
                    cpu_power_chart.append(cpu_power_percent)

                    gpu_power_percent = int(
                        cpu_metrics_dict["gpu_W"]/args.interval/gpu_max_power*100)
                    gpu_power_W = cpu_metrics_dict["gpu_W"]/args.interval
                    if gpu_power_W > gpu_peak_power:
                        gpu_peak_power = gpu_power_W
                    avg_gpu_power_list.append(gpu_power_W)
                    avg_gpu_power = get_avg(avg_gpu_power_list)
                    gpu_power_chart.title = "".join([
                        "GPU: ",
                        '{0:.2f}'.format(gpu_power_W),
                        "W (avg: ",
                        '{0:.2f}'.format(avg_gpu_power),
                        "W peak: ",
                        '{0:.2f}'.format(gpu_peak_power),
                        "W)"
                    ])
                    gpu_power_chart.append(gpu_power_percent)

                    ui.display()

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("Stopping...")

    return powermetrics_process


if __name__ == "__main__":
    powermetrics_process = main()
    try:
        powermetrics_process.terminate()
        print("Successfully terminated powermetrics process")
    except Exception as e:
        print(e)
        powermetrics_process.terminate()
        print("Successfully terminated powermetrics process")
