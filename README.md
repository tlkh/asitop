# asitop

Performance monitoring CLI tool for Apple Silicon

## What is `asitop`

An `nvtop`-inspired command line tool for Apple Silicon Macs.

* **CPU** — E-cluster and P-cluster utilization and frequency
* **GPU** — utilization and frequency
* **ANE** — utilization (measured by power)
* **Memory** — RAM and swap usage
* **Power** — CPU/GPU power with peak and rolling average

`asitop` uses the built-in [`powermetrics`](https://www.unix.com/man-page/osx/1/powermetrics/) utility on macOS. It requires `sudo` to run since `powermetrics` needs root access.

Works on all Apple Silicon Macs (M1 through M5 and beyond).

## Installation

### From source (requires Rust)

```shell
cd asitop-rs
cargo build --release
sudo cp target/release/asitop /usr/local/bin/asitop
```

### Pre-built binary

Download the latest binary from the [Releases](https://github.com/tlkh/asitop/releases) page and copy it to `/usr/local/bin/`.

## Usage

```shell
sudo asitop
```

Press `q` or `Esc` to exit.

## How it works

[`powermetrics`](https://www.unix.com/man-page/osx/1/powermetrics/) is used to measure:

* CPU/GPU utilization via active residency
* CPU/GPU frequency
* Package/CPU/GPU/ANE energy consumption

[`sysctl`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/sysctl.3.html) is used to measure:

* CPU name and core counts

[`system_profiler`](https://ss64.com/osx/system_profiler.html) is used to measure:

* GPU core count

## License

MIT
