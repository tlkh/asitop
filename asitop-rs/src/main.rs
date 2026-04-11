use std::collections::VecDeque;
use std::fs;
use std::io::{self, stdout};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result};
use crossterm::{
    event::{self, Event, KeyCode, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use plist::Value;
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame, Terminal,
};
use sysinfo::System;

// --- Data types ---

struct SocInfo {
    name: String,
    e_core_count: usize,
    p_core_count: usize,
    gpu_core_count: String,
    cpu_max_power: f64,
    gpu_max_power: f64,
}

struct CpuMetrics {
    e_active: u16,
    e_freq_mhz: u32,
    p_active: u16,
    p_freq_mhz: u32,
    ane_w: f64,
    cpu_w: f64,
    gpu_w: f64,
    package_w: f64,
}

struct GpuMetrics {
    active: u16,
    freq_mhz: u32,
}

struct RamMetrics {
    used_gb: f64,
    total_gb: f64,
    used_percent: u16,
    swap_used_gb: f64,
    swap_total_gb: f64,
}

struct AppState {
    soc: SocInfo,
    cpu: Option<CpuMetrics>,
    gpu: Option<GpuMetrics>,
    ram: RamMetrics,
    thermal: String,
    cpu_power_history: VecDeque<f64>,
    gpu_power_history: VecDeque<f64>,
    pkg_power_history: VecDeque<f64>,
    cpu_peak: f64,
    gpu_peak: f64,
    pkg_peak: f64,
}

// --- System info ---

fn run_sysctl(key: &str) -> Option<String> {
    let out = Command::new("sysctl").arg("-n").arg(key).output().ok()?;
    Some(String::from_utf8_lossy(&out.stdout).trim().to_string())
}

fn get_gpu_cores() -> String {
    Command::new("system_profiler")
        .args(["-detailLevel", "basic", "SPDisplaysDataType"])
        .output()
        .ok()
        .and_then(|o| {
            let s = String::from_utf8_lossy(&o.stdout);
            s.lines()
                .find(|l| l.contains("Total Number of Cores"))
                .and_then(|l| l.split(": ").last())
                .map(|v| v.trim().to_string())
        })
        .unwrap_or_else(|| "?".to_string())
}

fn get_soc_info() -> SocInfo {
    let name = run_sysctl("machdep.cpu.brand_string").unwrap_or_else(|| "Unknown".into());
    let e_core_count: usize = run_sysctl("hw.perflevel1.logicalcpu")
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);
    let p_core_count: usize = run_sysctl("hw.perflevel0.logicalcpu")
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);
    let gpu_core_count = get_gpu_cores();

    let (cpu_max_power, gpu_max_power) = match name.as_str() {
        "Apple M1" => (20.0, 20.0),
        "Apple M1 Pro" => (30.0, 30.0),
        "Apple M1 Max" => (30.0, 60.0),
        "Apple M1 Ultra" => (60.0, 120.0),
        "Apple M2" => (25.0, 15.0),
        _ => (30.0, 30.0),
    };

    SocInfo {
        name,
        e_core_count,
        p_core_count,
        gpu_core_count,
        cpu_max_power,
        gpu_max_power,
    }
}

// --- powermetrics ---

fn start_powermetrics(interval_ms: u32, path: &str) -> Result<Child> {
    // Clean up old files
    for entry in glob::iter("/tmp/asitop_powermetrics*") {
        let _ = fs::remove_file(entry);
    }

    Command::new("powermetrics")
        .args([
            "--samplers",
            "cpu_power,gpu_power,thermal",
            "-f",
            "plist",
            "-i",
            &interval_ms.to_string(),
            "-o",
            path,
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .context("Failed to start powermetrics (are you running with sudo?)")
}

fn parse_metrics(path: &str, interval: f64) -> Option<(CpuMetrics, GpuMetrics, String)> {
    let data = fs::read(path).ok()?;
    let parts: Vec<&[u8]> = data.split(|&b| b == 0).filter(|p| !p.is_empty()).collect();
    let last = *parts.last()?;
    let root: Value = plist::from_bytes(last).ok()?;
    let dict = root.as_dictionary()?;

    // Thermal
    let thermal = dict
        .get("thermal_pressure")
        .and_then(|v| v.as_string())
        .unwrap_or("Unknown")
        .to_string();

    // CPU
    let processor = dict.get("processor")?.as_dictionary()?;
    let clusters = processor.get("clusters")?.as_array()?;

    let mut e_actives: Vec<u16> = Vec::new();
    let mut e_freqs: Vec<u32> = Vec::new();
    let mut p_actives: Vec<u16> = Vec::new();
    let mut p_freqs: Vec<u32> = Vec::new();

    for cluster in clusters {
        let c = cluster.as_dictionary()?;
        let name = c.get("name")?.as_string()?;
        let freq = (c.get("freq_hz")?.as_real().or_else(|| c.get("freq_hz")?.as_signed_integer().map(|i| i as f64))? / 1e6) as u32;
        let idle = c.get("idle_ratio")?.as_real()?;
        let active = ((1.0 - idle) * 100.0) as u16;

        if name.starts_with('P') {
            p_actives.push(active);
            p_freqs.push(freq);
        } else {
            e_actives.push(active);
            e_freqs.push(freq);
        }
    }

    let e_active = if e_actives.is_empty() {
        0
    } else {
        (e_actives.iter().map(|&v| v as u32).sum::<u32>() / e_actives.len() as u32) as u16
    };
    let e_freq = e_freqs.iter().copied().max().unwrap_or(0);
    let p_active = if p_actives.is_empty() {
        0
    } else {
        (p_actives.iter().map(|&v| v as u32).sum::<u32>() / p_actives.len() as u32) as u16
    };
    let p_freq = p_freqs.iter().copied().max().unwrap_or(0);

    let get_energy = |key: &str| -> f64 {
        processor
            .get(key)
            .and_then(|v| v.as_real().or_else(|| v.as_signed_integer().map(|i| i as f64)))
            .unwrap_or(0.0)
            / 1000.0
            / interval
    };

    let cpu = CpuMetrics {
        e_active,
        e_freq_mhz: e_freq,
        p_active,
        p_freq_mhz: p_freq,
        ane_w: get_energy("ane_energy"),
        cpu_w: get_energy("cpu_energy"),
        gpu_w: get_energy("gpu_energy"),
        package_w: {
            processor
                .get("combined_power")
                .and_then(|v| v.as_real().or_else(|| v.as_signed_integer().map(|i| i as f64)))
                .unwrap_or(0.0)
                / 1000.0
        },
    };

    // GPU
    let gpu_dict = dict.get("gpu")?.as_dictionary()?;
    let gpu_freq = gpu_dict
        .get("freq_hz")
        .and_then(|v| v.as_real().or_else(|| v.as_signed_integer().map(|i| i as f64)))
        .unwrap_or(0.0) as u32;
    let gpu_idle = gpu_dict.get("idle_ratio")?.as_real()?;
    let gpu = GpuMetrics {
        active: ((1.0 - gpu_idle) * 100.0) as u16,
        freq_mhz: gpu_freq,
    };

    Some((cpu, gpu, thermal))
}

// --- RAM ---

fn get_ram_metrics() -> RamMetrics {
    let mut sys = System::new();
    sys.refresh_memory();

    let total = sys.total_memory() as f64;
    let used = sys.used_memory() as f64;
    let swap_total = sys.total_swap() as f64;
    let swap_used = sys.used_swap() as f64;
    let gb = 1024.0 * 1024.0 * 1024.0;

    RamMetrics {
        used_gb: used / gb,
        total_gb: total / gb,
        used_percent: if total > 0.0 {
            (used / total * 100.0) as u16
        } else {
            0
        },
        swap_used_gb: swap_used / gb,
        swap_total_gb: swap_total / gb,
    }
}

// --- UI ---

fn make_bar(width: u16, percent: u16, color: Color) -> Line<'static> {
    let pct = percent.min(100) as usize;
    let total = width as usize;
    let filled = (total * pct) / 100;
    let empty = total - filled;
    Line::from(vec![
        Span::styled("█".repeat(filled), Style::default().fg(color)),
        Span::styled("░".repeat(empty), Style::default().fg(Color::DarkGray)),
    ])
}

fn render_row(frame: &mut Frame, area: Rect, label: &str, percent: u16, info: &str, color: Color) {
    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Length(16),
            Constraint::Min(10),
            Constraint::Length(16),
        ])
        .split(area);

    frame.render_widget(
        Paragraph::new(label.to_string()).style(Style::default().fg(Color::White)),
        cols[0],
    );

    let bar_width = cols[1].width.saturating_sub(2);
    let bar = make_bar(bar_width, percent, color);
    frame.render_widget(
        Paragraph::new(vec![bar]),
        Rect { x: cols[1].x + 1, width: bar_width, ..cols[1] },
    );

    frame.render_widget(
        Paragraph::new(format!(" {}", info)).style(Style::default().fg(Color::Gray)),
        cols[2],
    );
}

fn ui(frame: &mut Frame, state: &AppState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(6),
            Constraint::Length(3),
            Constraint::Length(5),
        ])
        .split(frame.area());

    // --- Processor ---
    let proc_title = format!(
        " {} ({}E+{}P+{}GPU) ",
        state.soc.name, state.soc.e_core_count, state.soc.p_core_count, state.soc.gpu_core_count
    );
    let proc_block = Block::default()
        .title(proc_title)
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::Cyan));
    let proc_inner = proc_block.inner(chunks[0]);
    frame.render_widget(proc_block, chunks[0]);

    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
        ])
        .split(proc_inner);

    if let Some(cpu) = &state.cpu {
        render_row(frame, rows[0],
            &format!(" E-CPU {:>3}%", cpu.e_active),
            cpu.e_active,
            &format!("{} MHz", cpu.e_freq_mhz),
            Color::Green);
        render_row(frame, rows[1],
            &format!(" P-CPU {:>3}%", cpu.p_active),
            cpu.p_active,
            &format!("{} MHz", cpu.p_freq_mhz),
            Color::Green);
    }

    if let Some(gpu) = &state.gpu {
        render_row(frame, rows[2],
            &format!(" GPU   {:>3}%", gpu.active),
            gpu.active,
            &format!("{} MHz", gpu.freq_mhz),
            Color::Magenta);
    }

    let ane_w = state.cpu.as_ref().map(|c| c.ane_w).unwrap_or(0.0);
    frame.render_widget(
        Paragraph::new(format!(" ANE   {:.2} W", ane_w)).style(Style::default().fg(Color::Yellow)),
        rows[3],
    );

    // --- Memory ---
    let swap_str = if state.ram.swap_total_gb < 0.1 {
        "swap inactive".to_string()
    } else {
        format!("{:.1}/{:.1}GB", state.ram.swap_used_gb, state.ram.swap_total_gb)
    };
    let mem_block = Block::default()
        .title(" Memory ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::Cyan));
    let mem_inner = mem_block.inner(chunks[1]);
    frame.render_widget(mem_block, chunks[1]);

    render_row(frame, mem_inner,
        &format!(" RAM {:.1}/{:.1}GB", state.ram.used_gb, state.ram.total_gb),
        state.ram.used_percent,
        &swap_str,
        Color::Blue);

    // --- Power ---
    let avg = |dq: &VecDeque<f64>| -> f64 {
        if dq.is_empty() { 0.0 } else { dq.iter().sum::<f64>() / dq.len() as f64 }
    };

    let cpu_w = state.cpu.as_ref().map(|c| c.cpu_w).unwrap_or(0.0);
    let gpu_w = state.cpu.as_ref().map(|c| c.gpu_w).unwrap_or(0.0);
    let pkg_w = state.cpu.as_ref().map(|c| c.package_w).unwrap_or(0.0);

    let thermal_str = if state.thermal == "Nominal" { "no" } else { "YES" };
    let power_title = format!(
        " Power | Package {:.1}W (avg {:.1}W peak {:.1}W) | Throttle: {} ",
        pkg_w, avg(&state.pkg_power_history), state.pkg_peak, thermal_str
    );

    let power_block = Block::default()
        .title(power_title)
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::Cyan));
    let power_inner = power_block.inner(chunks[2]);
    frame.render_widget(power_block, chunks[2]);

    let ane_w = state.cpu.as_ref().map(|c| c.ane_w).unwrap_or(0.0);

    let power_rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(1), Constraint::Length(1), Constraint::Length(1)])
        .split(power_inner);

    let cpu_pct = ((cpu_w / state.soc.cpu_max_power) * 100.0).min(100.0) as u16;
    render_row(frame, power_rows[0],
        &format!(" CPU  {:.2}W", cpu_w),
        cpu_pct,
        &format!("avg {:.1} pk {:.1}", avg(&state.cpu_power_history), state.cpu_peak),
        Color::Red);

    let gpu_pct = ((gpu_w / state.soc.gpu_max_power) * 100.0).min(100.0) as u16;
    render_row(frame, power_rows[1],
        &format!(" GPU  {:.2}W", gpu_w),
        gpu_pct,
        &format!("avg {:.1} pk {:.1}", avg(&state.gpu_power_history), state.gpu_peak),
        Color::Red);

    frame.render_widget(
        Paragraph::new(format!(" ANE  {:.2}W", ane_w)).style(Style::default().fg(Color::Yellow)),
        power_rows[2],
    );
}

// --- Glob helper (no extra dep) ---

mod glob {
    use std::path::PathBuf;

    pub fn iter(pattern: &str) -> impl Iterator<Item = PathBuf> {
        let dir = std::path::Path::new(pattern)
            .parent()
            .unwrap_or(std::path::Path::new("/tmp"));
        let prefix = pattern
            .rsplit('/')
            .next()
            .unwrap_or("")
            .trim_end_matches('*');
        let entries: Vec<PathBuf> = std::fs::read_dir(dir)
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .map(|e| e.path())
            .filter(move |p| {
                p.file_name()
                    .and_then(|n| n.to_str())
                    .is_some_and(|n| n.starts_with(prefix))
            })
            .collect();
        entries.into_iter()
    }
}

// --- Main ---

fn main() -> Result<()> {
    let interval_secs: f64 = 1.0;
    let interval_ms: u32 = (interval_secs * 1000.0) as u32;
    let avg_window: usize = 30;

    let soc = get_soc_info();

    let timecode = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
        .to_string();
    let metrics_path = format!("/tmp/asitop_powermetrics{}", timecode);

    let mut pm_process = start_powermetrics(interval_ms, &metrics_path)?;

    // Wait for first reading
    let mut first_reading = None;
    for _ in 0..30 {
        if let Some(m) = parse_metrics(&metrics_path, interval_secs) {
            first_reading = Some(m);
            break;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    if first_reading.is_none() {
        let _ = pm_process.kill();
        anyhow::bail!("Timed out waiting for powermetrics data");
    }

    let (cpu, gpu, thermal) = first_reading.unwrap();

    let mut state = AppState {
        soc,
        cpu: Some(cpu),
        gpu: Some(gpu),
        ram: get_ram_metrics(),
        thermal,
        cpu_power_history: VecDeque::with_capacity(avg_window),
        gpu_power_history: VecDeque::with_capacity(avg_window),
        pkg_power_history: VecDeque::with_capacity(avg_window),
        cpu_peak: 0.0,
        gpu_peak: 0.0,
        pkg_peak: 0.0,
    };

    // Setup terminal
    enable_raw_mode()?;
    let mut stdout = stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let cleanup = || -> Result<()> {
        disable_raw_mode()?;
        execute!(io::stdout(), LeaveAlternateScreen)?;
        Ok(())
    };

    loop {
        // Poll for input
        if event::poll(Duration::from_millis(interval_ms as u64))? {
            if let Event::Key(key) = event::read()? {
                if key.code == KeyCode::Char('q')
                    || key.code == KeyCode::Esc
                    || (key.code == KeyCode::Char('c')
                        && key.modifiers.contains(KeyModifiers::CONTROL))
                {
                    break;
                }
            }
        }

        // Update metrics
        if let Some((cpu, gpu, thermal)) = parse_metrics(&metrics_path, interval_secs) {
            // Track power history
            let push_bounded = |dq: &mut VecDeque<f64>, val: f64, max: usize| {
                if dq.len() >= max {
                    dq.pop_front();
                }
                dq.push_back(val);
            };
            push_bounded(&mut state.cpu_power_history, cpu.cpu_w, avg_window);
            push_bounded(&mut state.gpu_power_history, cpu.gpu_w, avg_window);
            push_bounded(&mut state.pkg_power_history, cpu.package_w, avg_window);

            if cpu.cpu_w > state.cpu_peak {
                state.cpu_peak = cpu.cpu_w;
            }
            if cpu.gpu_w > state.gpu_peak {
                state.gpu_peak = cpu.gpu_w;
            }
            if cpu.package_w > state.pkg_peak {
                state.pkg_peak = cpu.package_w;
            }

            state.cpu = Some(cpu);
            state.gpu = Some(gpu);
            state.thermal = thermal;
        }
        state.ram = get_ram_metrics();

        terminal.draw(|f| ui(f, &state))?;
    }

    cleanup()?;
    let _ = pm_process.kill();
    let _ = pm_process.wait();
    let _ = fs::remove_file(&metrics_path);

    Ok(())
}
