import os
import glob
import subprocess
from subprocess import PIPE
import psutil
from .parsers import (
    parse_thermal_pressure,
    parse_cpu_metrics,
    parse_gpu_metrics,
)
import plistlib


def parse_powermetrics(path='/tmp/asitop_powermetrics', timecode="0"):
    """Parse the most recent plist entry from the powermetrics output file.

    powermetrics appends plist entries separated by null bytes (\\x00) to a
    continuously growing file. The previous implementation read the *entire*
    file on every call (once per second by default), then split all contents
    into memory. After multi-day runs the file grows into gigabytes, causing
    asitop to consume 6 GB+ RSS (observed on an M4 Mac mini after ~3 days).

    This implementation seeks to the end of the file and reads *backwards* in
    64 KB chunks until it has found at least two null-byte-separated segments.
    Only those final segments are loaded into memory, so memory usage stays
    constant regardless of how long asitop has been running.
    """
    CHUNK_SIZE = 65536  # 64 KB — larger than any single powermetrics plist entry

    try:
        with open(path + timecode, 'rb') as fp:
            fp.seek(0, 2)
            file_size = fp.tell()

            if file_size == 0:
                return False

            # Read backwards in chunks until we have ≥2 null-byte separators.
            # With ≥2 separators we get ≥3 segments, guaranteeing both a
            # primary candidate (segments[-1]) and a fallback (segments[-2]).
            tail = b''
            pos = file_size

            while pos > 0:
                read_size = min(CHUNK_SIZE, pos)
                pos -= read_size
                fp.seek(pos)
                tail = fp.read(read_size) + tail
                if tail.count(b'\x00') >= 2:
                    break

        segments = tail.split(b'\x00')

    except Exception:
        return False

    def _parse_segment(segment):
        """Parse a single plist segment, returning the metrics tuple or None."""
        segment = segment.strip(b'\x00')
        if not segment:
            return None
        try:
            powermetrics_parse = plistlib.loads(segment)
            thermal_pressure = parse_thermal_pressure(powermetrics_parse)
            cpu_metrics_dict = parse_cpu_metrics(powermetrics_parse)
            gpu_metrics_dict = parse_gpu_metrics(powermetrics_parse)
            # bandwidth_metrics = parse_bandwidth_metrics(powermetrics_parse)
            bandwidth_metrics = None
            timestamp = powermetrics_parse["timestamp"]
            return cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, bandwidth_metrics, timestamp
        except Exception:
            return None

    # Try segments from most-recent to oldest; the very last segment may be
    # a partial write in progress, so fall back to earlier complete entries.
    for segment in reversed(segments):
        result = _parse_segment(segment)
        if result is not None:
            return result

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
        os.remove(tmpf)
    output_file_flag = "-o"
    command = " ".join([
        "sudo nice -n",
        str(nice),
        "powermetrics",
        "--samplers cpu_power,gpu_power,thermal",
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
