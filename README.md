# Windows Health Checker

A comprehensive Windows system health monitoring tool with a modern dark-themed interface.

![Windows 10/11](https://img.shields.io/badge/Windows-10%2F11-blue)
![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Download

**[⬇️ Download Latest Release](https://github.com/rshearer1/SimpleWindowsHealth/releases/latest)**

No installation required - just download and run!

## What It Does

Windows Health Checker scans your system and provides actionable insights across 9 key areas:

| Module | What It Checks |
|--------|----------------|
| **Drivers** | Outdated, unsigned, or problematic drivers |
| **Startup** | Programs that slow down your boot time |
| **Updates** | Pending Windows updates and update history |
| **Storage** | Drive health, free space, and usage warnings |
| **Security** | Windows Defender, Firewall status, UAC settings |
| **Hardware** | CPU, GPU, RAM info with real-time monitoring |
| **System** | OS details, system file integrity (SFC/DISM) |
| **Events** | Recent errors and warnings from system logs |
| **Audio** | Audio device status and troubleshooting |

## Key Features

- **One-Click Full Scan** - Analyzes all modules simultaneously
- **Real-Time Monitoring** - Live CPU, RAM, and disk usage graphs
- **Dark Theme UI** - Easy on the eyes, modern design
- **No Installation** - Portable executable, runs anywhere
- **Actionable Results** - Direct links to fix issues or open system tools

## System Requirements

- Windows 10 or Windows 11
- Administrator privileges recommended for full functionality

## Running from Source

```bash
git clone https://github.com/rshearer1/SimpleWindowsHealth.git
cd SimpleWindowsHealth
pip install PyQt6 psutil wmi
python driver_updater_qt_mk5.py
```

## Building the Executable

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "WindowsHealthChecker" driver_updater_qt_mk5.py
```

## Changelog

### v2.0.1
- Fixed console window briefly appearing during scans

### v2.1.0
- Added Firewall rules viewer
- Enhanced Security page with tabbed layout
- Improved UI consistency across all pages

### v2.0.0
- Complete UI redesign
- Parallel scanning for faster results
- Added Event log analysis
- Enhanced hardware monitoring with live graphs

### v1.0.0
- Initial release

## Contributing

Contributions welcome! Fork the repo and submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

Found a bug? [Open an issue](https://github.com/rshearer1/SimpleWindowsHealth/issues).
