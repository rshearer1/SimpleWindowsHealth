# Windows Health Checker Pro

<div align="center">

**The all-in-one Windows system diagnostics and optimization tool**

[![Windows 10/11](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows)](https://www.microsoft.com/windows)
[![Version](https://img.shields.io/badge/Version-4.0.0-green?style=for-the-badge)](https://github.com/rshearer1/SimpleWindowsHealth/releases/latest)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/rshearer1/SimpleWindowsHealth/total?style=for-the-badge&color=blue)](https://github.com/rshearer1/SimpleWindowsHealth/releases)

[**⬇️ Download Latest Release**](https://github.com/rshearer1/SimpleWindowsHealth/releases/latest)

*No installation required - just download and run!*

</div>

---

## 🎯 What is Windows Health Checker Pro?

Windows Health Checker Pro is a **free, portable system utility** that gives you complete visibility into your PC's health. With one click, scan your entire system and get actionable insights to fix problems, optimize performance, and keep Windows running smoothly.

### Why Use This Tool?

- ✅ **No installation** - Single portable executable
- ✅ **No telemetry** - Your data stays on your machine
- ✅ **No bloatware** - Clean, focused functionality
- ✅ **Modern UI** - Beautiful dark/light theme with accent colors
- ✅ **Custom Icon** - Heart with pulse design for easy identification
- ✅ **Fast** - Parallel scanning completes in seconds
- ✅ **Comprehensive** - 10+ diagnostic modules in one tool

---

## ✨ Features

### 🔍 One-Click Full System Scan

Run all diagnostics simultaneously with parallel execution:

| Module | What It Checks |
|--------|----------------|
| 🖥️ **Overview** | Health score, live CPU/RAM/Disk graphs, quick status cards |
| 🔧 **Drivers** | Outdated, unsigned, or problematic drivers with manufacturer details |
| 🚀 **Startup** | Boot programs with impact ratings - enable/disable directly |
| 🔄 **Windows Updates** | Pending updates, update history, service status |
| 💾 **Storage** | Drive health, SMART status, space warnings, cleanup tools |
| 🛡️ **Security** | Defender, Firewall profiles & rules, UAC, BitLocker, Secure Boot |
| 📦 **Software** | Installed apps via Winget - search, install, and update packages |
| 🖱️ **Hardware** | CPU, GPU, RAM, motherboard with real-time monitoring |
| ⚙️ **System** | OS info, restore points, SFC/DISM integrity checks |
| ⚠️ **Events** | Critical errors and warnings from Windows Event Logs |
| 🔊 **Audio** | Audio devices, speaker test, troubleshooting |

### 📊 Real-Time Dashboard

- **Health Score** - Overall system health at a glance (0-100)
- **Live Metrics** - CPU, RAM, and Disk usage with animated graphs
- **Quick Status Cards** - Instant visibility into key system areas
- **Tips Carousel** - Rotating Windows health and security tips

### 🎨 Beautiful Modern Interface

- **Dark & Light Themes** - Choose your preferred look
- **6 Accent Colors** - Blue, Green, Purple, Orange, Pink, or Teal
- **Glass-effect Cards** - Modern translucent design elements
- **Smooth Animations** - Polished, responsive interactions
- **Clean Sidebar** - Intuitive navigation with icons

### 🛠️ Built-in Quick Tools

Launch Windows utilities directly from the app:

- Task Manager
- Device Manager  
- Disk Cleanup
- Windows Update
- Windows Security
- System Properties
- Event Viewer
- Sound Settings
- Control Panel
- Storage Sense

### 📦 Software Management (Winget Integration)

- **Search** packages from Windows Package Manager
- **Install** apps with one click
- **Check for Updates** on installed software
- **Update All** outdated packages at once

---

## 📸 Screenshots

<div align="center">

| Overview Dashboard | Security Analysis |
|:------------------:|:-----------------:|
| *Health score, live graphs, quick status* | *Defender, Firewall, BitLocker status* |

| Startup Manager | Hardware Info |
|:---------------:|:-------------:|
| *Enable/disable boot programs* | *CPU, GPU, RAM details* |

</div>

---

## 🚀 Getting Started

### Download & Run (Recommended)

1. **Download** [`WindowsHealthCheckerPro.exe`](https://github.com/rshearer1/SimpleWindowsHealth/releases/latest) from Releases
2. **Run** the executable - no installation needed
3. **Click** "Run Full Scan" to check your system
4. **Explore** results in each module page

> 💡 **Tip:** Run as Administrator for full functionality (driver details, startup management, system file checks)

### Run from Source

```bash
# Clone the repository
git clone https://github.com/rshearer1/SimpleWindowsHealth.git
cd SimpleWindowsHealth

# Install dependencies
pip install PyQt6 psutil wmi

# Run the application
python driver_updater_qt_mk5.py
```

---

## 💻 System Requirements

| Requirement | Minimum |
|-------------|---------|
| **Operating System** | Windows 10 (1809+) or Windows 11 |
| **Privileges** | Standard user (Admin recommended for full features) |
| **Disk Space** | ~40 MB |
| **RAM** | 100 MB |
| **Display** | 1280x720 or higher |

---

## 📖 Feature Guide

### Overview Page
The main dashboard shows your system health at a glance with a calculated health score, real-time performance graphs, and quick status cards for each major category.

### Startup Manager
View all programs that run at Windows startup. See their impact rating (High/Medium/Low) and disable unnecessary ones to speed up boot time. Changes take effect on next restart.

### Security Center
Three-tab layout covering:
- **Windows Defender** - Real-time protection, scan status, definition updates
- **Firewall Status** - Domain/Private/Public network profiles
- **Firewall Rules** - Active inbound/outbound rules with port and protocol details

### Storage Analysis
Monitor all drives with visual usage bars. Color-coded warnings for low space. View SMART health data for SSDs and HDDs. Quick access to Disk Cleanup and Storage Sense.

### Software Updates (Winget)
Integrates with Windows Package Manager to show available updates for installed software. Update individual apps or all at once.

### Settings
Customize your experience:
- **Theme** - Dark or Light mode
- **Accent Color** - 6 color options
- Toggle various scan options

---

## 🔧 Building from Source

```bash
# Install build dependencies
pip install pyinstaller PyQt6 psutil wmi

# Build using the spec file
python -m PyInstaller --clean --noconfirm WindowsHealthCheckerPro.spec

# Executable will be in dist/WindowsHealthCheckerPro.exe
```

---

## 📋 Changelog

### v4.0.0 (December 2025) - Latest
- 💜 **Custom App Icon** - Heart with pulse design for taskbar and window
- ✨ **Theme System** - Full Dark/Light mode support with proper card theming
- 🎨 **Accent Colors** - 6 customizable accent colors (Blue, Green, Purple, Orange, Pink, Teal)
- 📦 **Winget Integration** - Search, install, and update software via Windows Package Manager
- 🔄 **Update Checker** - Check for software updates across all installed apps
- 📄 **Architecture Documentation** - Code quality and performance review
- 🐛 Bug fixes and performance improvements

### v3.0.1
- Fixed update checking functionality
- Improved error handling
- Live accent color customization

### v3.0.0
- Major UI overhaul with glass-effect cards
- Added Software/Winget page
- Enhanced hardware monitoring
- New splash screen with loading progress
- Custom frameless title bar (Outlook-style)

### v2.0.0
- Complete UI redesign with modern dark theme
- Parallel scanning - all checks run simultaneously
- Added Firewall rules viewer
- Enhanced Security page with 3-tab layout
- Added Event log analysis
- Live performance graphs

### v1.0.0
- Initial release

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🐛 Support & Feedback

- 🐛 **Found a bug?** [Open an Issue](https://github.com/rshearer1/SimpleWindowsHealth/issues)
- 💡 **Have an idea?** [Start a Discussion](https://github.com/rshearer1/SimpleWindowsHealth/discussions)
- ⭐ **Like this tool?** Give it a star!

---

<div align="center">

**Made with ❤️ for Windows users who care about their system health**

[⬆ Back to Top](#windows-health-checker-pro)

</div>
