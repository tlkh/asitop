import os
import glob
import subprocess
from subprocess import PIPE
import psutil
from .parsers import *
import plistlib


def parse_powermetrics(path='/tmp/asitop_powermetrics', timecode="0"):
    data = None
    try:
        with open(path+timecode, 'rb') as fp:
            data = fp.read()
        data = data.split(b'\x00')
        powermetrics_parse = plistlib.loads(data[-1])
        thermal_pressure = parse_thermal_pressure(powermetrics_parse)
        cpu_metrics_dict = parse_cpu_metrics(powermetrics_parse)
        gpu_metrics_dict = parse_gpu_metrics(powermetrics_parse)
        # bandwidth_metrics = parse_bandwidth_metrics(powermetrics_parse)
        network_metrics_dict = parse_network_metrics(powermetrics_parse)
        disk_metrics_dict = parse_disk_metrics(powermetrics_parse)
        timestamp = powermetrics_parse["timestamp"]
        return cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, network_metrics_dict, disk_metrics_dict, timestamp
    except Exception as e:
        if data:
            if len(data) > 1:
                powermetrics_parse = plistlib.loads(data[-2])
                thermal_pressure = parse_thermal_pressure(powermetrics_parse)
                cpu_metrics_dict = parse_cpu_metrics(powermetrics_parse)
                gpu_metrics_dict = parse_gpu_metrics(powermetrics_parse)
                # bandwidth_metrics = parse_bandwidth_metrics(powermetrics_parse)
                network_metrics_dict = parse_network_metrics(powermetrics_parse)
                disk_metrics_dict = parse_disk_metrics(powermetrics_parse)
                timestamp = powermetrics_parse["timestamp"]
                return cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, network_metrics_dict, disk_metrics_dict, timestamp
        return False


def clear_console():
    command = 'clear'
    os.system(command)


def convert_to_GB(value):
    return round(value/1024/1024/1024, 1)


def run_powermetrics_process(timecode, nice=10, interval=1000):
    #ver, *_ = platform.mac_ver()
    #major_ver = int(ver.split(".")[0])
    for tmpf in glob.glob("/tmp/asitop_powermetrics*"):
        subprocess.Popen(["sudo","rm",tmpf])
    output_file_flag = "-o"
    command = " ".join([
        "sudo nice -n",
        str(nice),
        "powermetrics",
        "--samplers cpu_power,gpu_power,thermal,disk,network",
        output_file_flag,
        "/tmp/asitop_powermetrics"+timecode,
        "-f plist",
        "-i",
        str(interval)
    ])
    process = subprocess.Popen(command.split(" "), stdin=PIPE, stdout=PIPE)
    return process


def get_ram_metrics_dict():
    ram_metrics = psutil.virtual_memory()
    swap_metrics = psutil.swap_memory()
    total_GB = convert_to_GB(ram_metrics.total)
    free_GB = convert_to_GB(ram_metrics.available)
    used_GB = convert_to_GB(ram_metrics.total-ram_metrics.available)
    swap_total_GB = convert_to_GB(swap_metrics.total)
    swap_used_GB = convert_to_GB(swap_metrics.used)
    swap_free_GB = convert_to_GB(swap_metrics.total-swap_metrics.used)
    if swap_total_GB > 0:
        swap_free_percent = int(100-(swap_free_GB/swap_total_GB*100))
    else:
        swap_free_percent = None
    ram_metrics_dict = {
        "total_GB": round(total_GB, 1),
        "free_GB": round(free_GB, 1),
        "used_GB": round(used_GB, 1),
        "free_percent": int(100-(ram_metrics.available/ram_metrics.total*100)),
        "swap_total_GB": swap_total_GB,
        "swap_used_GB": swap_used_GB,
        "swap_free_GB": swap_free_GB,
        "swap_free_percent": swap_free_percent,
    }
    return ram_metrics_dict


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

def get_disk_info():
    """Returns disk capacity in GB
    """
    total,used,free,percent=psutil.disk_usage('/')
    total_GB=total/(1024**3)
    possible_disk_capacities=[256,512,1024,2048,4096,8192]
    #256G might be 240~ G here, so we do this
    for p in possible_disk_capacities:
        if p>total_GB:
            return p
    #TODO: However, it cannot handle things correctly all the time if the disk is partitioned, for example, installed Asahi Linux.

def get_core_counts():
    cores_info = os.popen('sysctl -a | grep hw.perflevel').read()
    cores_info_lines = cores_info.split("\n")
    data_fields = ["hw.perflevel0.logicalcpu", "hw.perflevel1.logicalcpu"]
    cores_info_dict = {}
    for l in cores_info_lines:
        for h in data_fields:
            if h in l:
                value = int(l.split(":")[1].strip())
                cores_info_dict[h] = value
    return cores_info_dict


def get_gpu_cores():
    try:
        cores = os.popen(
            "system_profiler -detailLevel basic SPDisplaysDataType | grep 'Total Number of Cores'").read()
        cores = int(cores.split(": ")[-1])
    except:
        cores = "?"
    return cores


def get_soc_info():
    cpu_info_dict = get_cpu_info()
    core_counts_dict = get_core_counts()
    try:
        e_core_count = core_counts_dict["hw.perflevel1.logicalcpu"]
        p_core_count = core_counts_dict["hw.perflevel0.logicalcpu"]
    except:
        e_core_count = "?"
        p_core_count = "?"
    soc_info = {
        "name": cpu_info_dict["machdep.cpu.brand_string"],
        "core_count": int(cpu_info_dict["machdep.cpu.core_count"]),
        "cpu_max_power": None,
        "gpu_max_power": None,
        "cpu_max_bw": None,
        "gpu_max_bw": None,
        "e_core_count": e_core_count,
        "p_core_count": p_core_count,
        "gpu_core_count": get_gpu_cores()
    }
    #Theorically Thunderbolt4 can reach 5120 MByte/s, but who will ever use an Ethernet adaptor like that?
    soc_info["max_network_speed"]=128
    # TDP (power)
    if soc_info["name"] == "Apple M1 Max":
        soc_info["cpu_max_power"] = 30
        soc_info["gpu_max_power"] = 60
    elif soc_info["name"] == "Apple M1 Pro":
        soc_info["cpu_max_power"] = 30
        soc_info["gpu_max_power"] = 30
    elif soc_info["name"] == "Apple M1":
        soc_info["cpu_max_power"] = 20
        soc_info["gpu_max_power"] = 20
    elif soc_info["name"] == "Apple M1 Ultra":
        soc_info["cpu_max_power"] = 60
        soc_info["gpu_max_power"] = 120
    elif soc_info["name"] == "Apple M2":
        soc_info["cpu_max_power"] = 25
        soc_info["gpu_max_power"] = 15
    else:
        soc_info["cpu_max_power"] = 20
        soc_info["gpu_max_power"] = 20
    # bandwidth
    disk_capacity=get_disk_info()
    if soc_info["name"] in ["Apple M1 Max","Apple M1 Pro","Apple M1","Apple M1 Ultra"]:
        #According to https://forums.macrumors.com/threads/mbp-2021-ssd-speed-comparison-please-contribute.2320899/
        #In MByte/s
        write_speeds={
            256:2500,
            512:5000,
            1024:6000,
            2048:6500,
            4096:7500,
            8192:7500,
        }
        read_speeds={
            256:3000,
            512:5500,
            1024:5500,
            2048:5500,
            4096:6000,
            8192:6000,
        }
        soc_info["disk_write_max"]=write_speeds[disk_capacity]
        soc_info["disk_read_max"]=read_speeds[disk_capacity]
    elif soc_info["name"] in ["Apple M2"]:
        write_speeds={
            256:1500,
            512:5000,
            1024:6000,
            2048:6500,
            4096:7500,
            8192:7500,
        }
        read_speeds={
            256:1500,
            512:5500,
            1024:5500,
            2048:5500,
            4096:6000,
            8192:6000,
        }
        soc_info["disk_write_max"]=write_speeds[disk_capacity]
        soc_info["disk_read_max"]=read_speeds[disk_capacity]
    if soc_info["name"] == "Apple M1 Max":
        soc_info["cpu_max_bw"] = 250
        soc_info["gpu_max_bw"] = 400
    elif soc_info["name"] == "Apple M1 Pro":
        soc_info["cpu_max_bw"] = 200
        soc_info["gpu_max_bw"] = 200
    elif soc_info["name"] == "Apple M1":
        soc_info["cpu_max_bw"] = 70
        soc_info["gpu_max_bw"] = 70
    elif soc_info["name"] == "Apple M1 Ultra":
        soc_info["cpu_max_bw"] = 500
        soc_info["gpu_max_bw"] = 800
    elif soc_info["name"] == "Apple M2":
        soc_info["cpu_max_bw"] = 100
        soc_info["gpu_max_bw"] = 100
    else:
        soc_info["cpu_max_bw"] = 70
        soc_info["gpu_max_bw"] = 70
    return soc_info
