# Windows Health Checker Pro - UI/UX Specification

## Design Philosophy

This application draws inspiration from **Microsoft PowerToys**, **Windows Security**, and **Windows Terminal** — tools known for their clean, professional aesthetic. The goal is a UI that feels like a first-party Microsoft tool: purposeful, consistent, and refined.

---

## 1. Window Structure & Layout

### Primary Window Dimensions

- **Minimum Size**: 1100 × 720 px
- **Default Size**: 1280 × 800 px
- **Maximum Size**: Resizable to screen bounds

### Layout Architecture (Three-Panel Design)

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│  TITLE BAR (32px)                                            ─  □  ×       │
├──────────────┬──────────────────────────────────────────────────────────────┤
│              │  HEADER ZONE (64px)                                          │
│              │  ┌─────────────────────────────────────────────────────────┐ │
│              │  │ 🏥 System Health          [Run All Checks] [⚙ Settings] │ │
│              │  │ Last scan: Today 2:34 PM        Score: 94/100 ████████░ │ │
│              │  └─────────────────────────────────────────────────────────┘ │
│   SIDEBAR    ├──────────────────────────────────────────────────────────────┤
│   (240px)    │                                                              │
│              │  CONTENT AREA                                                │
│  ┌────────┐  │                                                              │
│  │Overview│  │  ┌─────────────────────────────────────────────────────────┐ │
│  ├────────┤  │  │                                                         │ │
│  │Updates │  │  │  Module content renders here based on                   │ │
│  ├────────┤  │  │  sidebar selection                                      │ │
│  │Storage │  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Security│  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Hardware│  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │System  │  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Events  │  │  │                                                         │ │
│  └────────┘  │  │                                                         │ │
│              │  └─────────────────────────────────────────────────────────┘ │
├──────────────┴──────────────────────────────────────────────────────────────┤
│  STATUS BAR (28px)   Ready  │  12 checks passed  │  2 warnings  │  0 errors │
└─────────────────────────────────────────────────────────────────────────────┘
```text

---

## 2. Color Palette - Material Design Dark Theme

**Based on:** https://m2.material.io/design/color/dark-theme.html

### Core Principles

1. **Dark Grey, Not Black** - Use `#121212` as base (not pure black)
2. **Elevation = Lighter** - Higher elevation surfaces are lighter via white overlay
3. **Desaturated Colors** - Use 200-tone colors for accessibility (4.5:1 contrast)
4. **Limited Accents** - Most space is dark; color used sparingly
5. **Text Opacity** - High 87%, Medium 60%, Disabled 38%

### Elevation Surface System

Material Design expresses elevation through progressively lighter surfaces:

| Elevation | Overlay | Hex Color | Semantic Assignment |
|-----------|---------|-----------|---------------------|
| 0dp | 0% | `#121212` | Window Background (BG_WINDOW) |
| 1dp | 5% | `#1e1e1e` | Sidebar Background (BG_SIDEBAR) |
| 2dp | 7% | `#222222` | Card Background (BG_CARD) |
| 3dp | 8% | `#242424` | - |
| 4dp | 9% | `#272727` | Hover States (BG_CARD_HOVER) |
| 6dp | 11% | `#2c2c2c` | Elevated Elements (BG_ELEVATED) |
| 8dp | 12% | `#2e2e2e` | - |
| 12dp | 14% | `#333333` | - |
| 16dp | 15% | `#383838` | - |
| 24dp | 16% | `#3d3d3d` | Dialogs/Modals (BG_DIALOG) |

### Text Hierarchy (Opacity-Based)

| Level | Opacity | Hex Approximation | Usage |
|-------|---------|-------------------|-------|
| High Emphasis | 87% | `#dedede` | Headings, important text |
| Medium Emphasis | 60% | `#9e9e9e` | Body text, descriptions |
| Disabled | 38% | `#636363` | Hints, inactive, timestamps |

### Primary Color (Purple 200 - Material Baseline)

```txt
PRIMARY         = #bb86fc    (Purple 200 - main accent)
PRIMARY_VARIANT = #3700b3    (Purple 700 - dark variant)
ON_PRIMARY      = #000000    (Text on primary surfaces)
```txt

### Accent/Secondary Colors (Desaturated)

```txt
ACCENT          = #82b1ff    (Blue 200 - Windows-inspired)
ACCENT_HOVER    = #448aff    (Blue A200)
ACCENT_LIGHT    = #b3e5fc    (Light Blue 100)
SECONDARY       = #03dac6    (Teal 200)
```

### Semantic Colors (Desaturated for Dark Theme)

| Status | Color | Hex | Background Overlay |
|--------|-------|-----|-------------------|
| Success | Green 300 | `#81c784` | `rgba(129,199,132,0.12)` |
| Warning | Orange 200 | `#ffcc80` | `rgba(255,204,128,0.12)` |
| Error | MD Dark Error | `#cf6679` | `rgba(207,102,121,0.12)` |
| Info | Blue 200 | `#82b1ff` | `rgba(130,177,255,0.12)` |
| Running | Purple 200 | `#bb86fc` | `rgba(187,134,252,0.12)` |

> **Note:** The error color `#cf6679` is the official Material Design dark theme error, created by applying a 40% white overlay to the light theme error (#b00020).

### Borders

```txt
BORDER        = #3a3a3a    (Subtle - 12% white on surface)
BORDER_LIGHT  = #454545    (Emphasis)
BORDER_ACCENT = #bb86fc    (Primary color for focus states)
```txt

### Shadow System

**Material Design Rule:** Shadows remain dark in dark theme (no light glows).

| Elevation | Blur | Offset Y | Opacity |
|-----------|------|----------|---------|
| Low (1-2dp) | 4px | 2px | 48 |
| Medium (4-6dp) | 8px | 2px | 64 |
| High (8-16dp) | 16px | 4px | 80 |
| Highest (24dp) | 24px | 8px | 96 |

---

### Legacy Color Palette (Deprecated)

The following was the original color scheme before Material Design adoption:

```
BACKGROUND LAYERS (OLD)
├── Window Background     #1b1b1f    
├── Sidebar Background    #232328    
├── Card Background       #2d2d32    
├── Hover State           #38383d    
└── Active/Selected       #0078d4    

TEXT HIERARCHY (OLD)
├── Primary Text          #ffffff    
├── Secondary Text        #b4b4b4    
├── Tertiary Text         #7a7a7a    
└── Disabled Text         #4a4a4a    

SEMANTIC COLORS (OLD - Saturated)
├── Success/Healthy       #0f9d58    
├── Warning/Attention     #f4b400    
├── Error/Critical        #db4437    
├── Info/Neutral          #4285f4    
└── In Progress           #8e44ad    
```

---

## 3. Typography System

### Font Stack

```
Primary:      "Segoe UI Variable", "Segoe UI", system-ui, sans-serif
Monospace:    "Cascadia Code", "Consolas", monospace
```

### Type Scale

| Element          | Size   | Weight    | Line Height | Letter Spacing |
|------------------|--------|-----------|-------------|----------------|
| Page Title       | 28px   | SemiBold  | 36px        | -0.5px         |
| Section Header   | 18px   | SemiBold  | 24px        | 0              |
| Card Title       | 14px   | SemiBold  | 20px        | 0              |
| Body Text        | 13px   | Regular   | 20px        | 0.1px          |
| Caption          | 11px   | Regular   | 16px        | 0.2px          |
| Button Label     | 13px   | SemiBold  | 20px        | 0.3px          |
| Monospace Data   | 12px   | Regular   | 18px        | 0              |

---

## 4. Spacing System (8px Grid)

```
SPACING TOKENS
├── xs    4px     (Tight internal padding)
├── sm    8px     (Between related elements)
├── md    16px    (Between groups)
├── lg    24px    (Section margins)
├── xl    32px    (Major section breaks)
└── xxl   48px    (Page-level padding)

COMPONENT SPACING
├── Card padding           20px
├── Card gap (between)     16px
├── Sidebar item padding   12px 16px
├── Button padding         10px 20px
├── Input padding          10px 14px
└── List item gap          2px
```

---

## 5. Component Library

### 5.1 Health Status Card (Primary Component)

```
┌─────────────────────────────────────────────────────────────┐
│  ┌────┐                                                     │
│  │ 🔒 │  Windows Defender                          ✓ Active │
│  └────┘  Real-time protection enabled                       │
│          Last scan: December 2, 2025                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Threat History    Quarantined: 0    Allowed: 0         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  [Run Quick Scan]                              [View Details]│
└─────────────────────────────────────────────────────────────┘

SPECIFICATIONS:
- Width: 100% of content area (max 600px per card)
- Padding: 20px
- Border radius: 8px
- Background: #2d2d32
- Border: 1px solid #3a3a3f (subtle)
- Icon container: 40×40px, rounded 8px, background #38383d
- Status indicator (top right): Colored dot + text
```

### 5.2 Sidebar Navigation Item

```
STATES:
┌─────────────────────────────────────┐
│  Default                            │
│  ┌─────────────────────────────────┐│
│  │ 📊  Overview                    ││
│  └─────────────────────────────────┘│
│  Background: transparent            │
│  Text: #b4b4b4                      │
├─────────────────────────────────────┤
│  Hover                              │
│  ┌─────────────────────────────────┐│
│  │ 📊  Overview                    ││
│  └─────────────────────────────────┘│
│  Background: #38383d                │
│  Text: #ffffff                      │
├─────────────────────────────────────┤
│  Selected                           │
│  ┌─────────────────────────────────┐│
│  │▌📊  Overview                    ││
│  └─────────────────────────────────┘│
│  Background: #0078d4 (10% opacity)  │
│  Left border: 3px solid #0078d4     │
│  Text: #ffffff                      │
│  Icon: #60cdff                      │
└─────────────────────────────────────┘
```

### 5.3 Status Indicator Chips

```
HEALTHY (Green)
┌────────────────────────┐
│  ● Healthy             │  Background: rgba(15,157,88,0.15)
└────────────────────────┘  Border: 1px solid rgba(15,157,88,0.3)
                            Text: #4caf50
                            Dot: #0f9d58

WARNING (Amber)
┌────────────────────────┐
│  ● Attention Needed    │  Background: rgba(244,180,0,0.15)
└────────────────────────┘  Border: 1px solid rgba(244,180,0,0.3)
                            Text: #ffc107
                            Dot: #f4b400

ERROR (Red)
┌────────────────────────┐
│  ● Critical Issue      │  Background: rgba(219,68,55,0.15)
└────────────────────────┘  Border: 1px solid rgba(219,68,55,0.3)
                            Text: #f44336
                            Dot: #db4437

RUNNING (Purple)
┌────────────────────────┐
│  ◐ Scanning...         │  Background: rgba(142,68,173,0.15)
└────────────────────────┘  Border: 1px solid rgba(142,68,173,0.3)
                            Text: #ab47bc
                            Icon: Animated spinner
```

### 5.4 Progress Indicators

```
DETERMINATE PROGRESS BAR
┌─────────────────────────────────────────────────────────────┐
│  SFC Scan                                              73%  │
│  ████████████████████████████░░░░░░░░░░░                    │
│  Scanning system files...                                   │
└─────────────────────────────────────────────────────────────┘

Specifications:
- Track: 6px height, #38383d background, 3px radius
- Fill: Gradient #0078d4 → #60cdff, 3px radius
- Animation: Subtle pulse on active fills

INDETERMINATE PROGRESS
┌─────────────────────────────────────────────────────────────┐
│  ░░░████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
└─────────────────────────────────────────────────────────────┘

Animation: Sliding highlight, 1.5s ease-in-out infinite
```

### 5.5 Buttons

```
PRIMARY BUTTON (Accent)
┌────────────────────┐
│   Run All Checks   │  Background: #0078d4
└────────────────────┘  Hover: #106ebe
                        Active: #005a9e
                        Text: #ffffff
                        Padding: 10px 24px
                        Radius: 6px

SECONDARY BUTTON (Outline)
┌────────────────────┐
│   View Details     │  Background: transparent
└────────────────────┘  Border: 1px solid #5a5a5f
                        Hover background: #38383d
                        Text: #ffffff
                        Padding: 10px 20px
                        Radius: 6px

GHOST BUTTON (Subtle)
┌────────────────────┐
│   Cancel           │  Background: transparent
└────────────────────┘  Hover: rgba(255,255,255,0.06)
                        Text: #b4b4b4
                        Padding: 10px 16px

ICON BUTTON
┌──────┐
│  ⚙   │  Size: 36×36px
└──────┘  Background: transparent
          Hover: #38383d
          Radius: 6px
```

---

## 6. Module Layouts

### 6.1 Overview Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   System Health Score                                                   │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                                                                 │   │
│   │        ╭─────────╮                                              │   │
│   │       ╱           ╲      94 / 100                               │   │
│   │      │   ██████   │      Your system is healthy                 │   │
│   │      │   ██████   │                                             │   │
│   │       ╲   ████   ╱       12 checks passed                       │   │
│   │        ╰─────────╯       2 items need attention                 │   │
│   │                                                                 │   │
│   │   [Run Full Scan]              Last scan: 2 hours ago           │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   Quick Status                                                          │
│   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐          │
│   │ ✓ Windows Update│ │ ✓ Defender      │ │ ⚠ Storage       │          │
│   │   Up to date    │ │   Protected     │ │   85% full      │          │
│   └─────────────────┘ └─────────────────┘ └─────────────────┘          │
│   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐          │
│   │ ✓ Drive Health  │ │ ✓ Memory        │ │ ✓ System Files  │          │
│   │   All drives OK │ │   4.2 GB free   │ │   No issues     │          │
│   └─────────────────┘ └─────────────────┘ └─────────────────┘          │
│                                                                         │
│   Recent Activity                                                       │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  ● 2:34 PM   SFC scan completed - No integrity violations       │   │
│   │  ● 2:30 PM   Windows Update check - 2 updates available         │   │
│   │  ● 2:28 PM   Defender scan completed - No threats               │   │
│   │  ● Yesterday SMART check completed - All drives healthy         │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Module Detail View (Example: Storage)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   💾 Storage Health                                        [Run Check]  │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Drive C: (System)                               ⚠ 85% Used     │   │
│   │  ─────────────────────────────────────────────────────────────  │   │
│   │                                                                 │   │
│   │  ████████████████████████████████████████░░░░░░░░              │   │
│   │  203 GB used of 238 GB                     35 GB free           │   │
│   │                                                                 │   │
│   │  SMART Status: Healthy    │    CHKDSK: No errors found          │   │
│   │  Temperature: 34°C        │    Power-on hours: 8,432            │   │
│   │                                                                 │   │
│   │  [Run CHKDSK]  [Disk Cleanup]  [Analyze Space]                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Drive D: (Data)                                 ✓ 42% Used     │   │
│   │  ─────────────────────────────────────────────────────────────  │   │
│   │                                                                 │   │
│   │  ██████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░              │   │
│   │  420 GB used of 1 TB                           580 GB free      │   │
│   │                                                                 │   │
│   │  SMART Status: Healthy    │    CHKDSK: No errors found          │   │
│   │                                                                 │   │
│   │  [Run CHKDSK]  [Analyze Space]                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Interaction Patterns

### 7.1 Navigation Flow

```
USER JOURNEY MAP:

[Launch App]
     │
     ▼
[Overview Dashboard] ◄────────────────────────────────────┐
     │                                                     │
     ├──► Click sidebar item ──► [Module Detail View]     │
     │         │                                           │
     │         └──► Click "Run Check" ──► [Scan Running]  │
     │                    │                                │
     │                    ▼                                │
     │              [Results Display]                      │
     │                    │                                │
     │                    └──► Click "Back" or sidebar ───┘
     │
     └──► Click "Run All Checks" ──► [Progress Modal]
                    │
                    ▼
              [All Results Summary]
```

### 7.2 Scan Interaction States

```
IDLE STATE
┌─────────────────────────────────────────────────┐
│  Windows Update                    [Check Now]  │
│  Last checked: 2 hours ago                      │
└─────────────────────────────────────────────────┘

RUNNING STATE
┌─────────────────────────────────────────────────┐
│  Windows Update                    [Cancel]     │
│  ◐ Checking for updates...                      │
│  ░░░████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
└─────────────────────────────────────────────────┘

COMPLETE STATE (Success)
┌─────────────────────────────────────────────────┐
│  Windows Update                ✓ Up to date     │
│  2 optional updates available                   │
│  [View Updates]  [Check Again]                  │
└─────────────────────────────────────────────────┘

COMPLETE STATE (Warning)
┌─────────────────────────────────────────────────┐
│  Windows Update              ⚠ Updates pending  │
│  3 updates ready to install                     │
│  [Install Updates]  [View Details]              │
└─────────────────────────────────────────────────┘

COMPLETE STATE (Error)
┌─────────────────────────────────────────────────┐
│  Windows Update               ✗ Check failed    │
│  Could not connect to update service            │
│  [Retry]  [Troubleshoot]                        │
└─────────────────────────────────────────────────┘
```

### 7.3 Modal Dialog (Run All Checks)

```
┌─────────────────────────────────────────────────────────────┐
│                                                         ✕   │
│   Running System Health Check                               │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  ✓  Windows Update            Complete              │   │
│   │  ✓  Windows Defender          Complete              │   │
│   │  ✓  System File Integrity     Complete              │   │
│   │  ◐  Drive SMART Health        Checking drive 2/3   │   │
│   │  ○  Memory Health             Pending               │   │
│   │  ○  Event Log Analysis        Pending               │   │
│   │  ○  Service Status            Pending               │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   Overall Progress                                          │
│   ████████████████████████░░░░░░░░░░░░░░░░░░░░░   54%      │
│                                                             │
│   Estimated time remaining: 45 seconds                      │
│                                                             │
│                              [Run in Background]  [Cancel]  │
└─────────────────────────────────────────────────────────────┘

Specifications:
- Modal width: 500px
- Backdrop: rgba(0,0,0,0.6) with blur
- Animation: Fade in 200ms, scale from 95% to 100%
```

---

## 8. Animations & Micro-interactions

### 8.1 Timing Curves

```
STANDARD EASING
├── ease-out     cubic-bezier(0, 0, 0.2, 1)     Entry animations
├── ease-in      cubic-bezier(0.4, 0, 1, 1)     Exit animations
├── ease-in-out  cubic-bezier(0.4, 0, 0.2, 1)   State changes
└── bounce       cubic-bezier(0.68, -0.55, 0.265, 1.55)  Playful feedback

DURATION
├── instant      0ms         Immediate feedback
├── fast         100ms       Micro-interactions (hover, focus)
├── normal       200ms       Standard transitions
├── slow         300ms       Page/view transitions
└── deliberate   400ms       Complex animations
```

### 8.2 Specific Animations

```
SIDEBAR SELECTION
- Left border: width 0 → 3px, 150ms ease-out
- Background: opacity 0 → 0.1, 150ms ease-out
- Icon color: transition 150ms

CARD HOVER (Depth version)
- Box shadow: transition 200ms ease-out
- Transform: translateY(-2px), 200ms ease-out
- Border color: subtle brightening

BUTTON PRESS
- Transform: scale(0.98), 100ms ease-in
- Background: darken 10%

STATUS DOT (Scanning)
- Animation: pulse (scale 1 → 1.2 → 1), 1s infinite

PROGRESS BAR FILL
- Width transition: 300ms ease-out
- Gradient shift animation: continuous 2s

PAGE TRANSITION
- Old page: opacity 1 → 0, translateX(0 → -20px), 200ms
- New page: opacity 0 → 1, translateX(20px → 0), 200ms

MODAL OPEN
- Backdrop: opacity 0 → 1, 200ms
- Modal: scale(0.95) → scale(1), opacity 0 → 1, 250ms ease-out

MODAL CLOSE
- Modal: scale(1) → scale(0.95), opacity 1 → 0, 150ms ease-in
- Backdrop: opacity 1 → 0, 150ms
```

### 8.3 Loading States

```
SKELETON LOADER (Before data loads)
┌─────────────────────────────────────────────────┐
│  ┌────┐  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │
│  │░░░░│  ░░░░░░░░░░░░░░░░░░░                    │
│  └────┘                                         │
│         ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     │
└─────────────────────────────────────────────────┘

Animation: Shimmer effect (gradient slide left → right, 1.5s infinite)
Colors: #2d2d32 base, #38383d highlight
```

---

## 9. Icons

### Icon Set Recommendation

Use **Fluent UI System Icons** (Microsoft's official icon set) for consistency with Windows.

### Icon Specifications

```
ICON SIZES
├── Navigation icons     20px
├── Card icons           24px
├── Status icons         16px
├── Action buttons       16px
└── Hero/Feature icons   48px

ICON STYLE
- Stroke weight: Regular (1.5px)
- Filled variants for selected/active states
- Consistent corner radius in icon design
```

### Module Icons

| Module               | Icon (Fluent)                  | Emoji Fallback |
|----------------------|--------------------------------|----------------|
| Overview             | GridRegular                    | 📊             |
| Windows Update       | ArrowDownloadRegular           | 📥             |
| System Files         | DocumentSearchRegular          | 📄             |
| Storage/Drives       | HardDriveRegular               | 💾             |
| Memory               | RamRegular                     | 🧠             |
| Security/Defender    | ShieldCheckmarkRegular         | 🛡️             |
| Events               | AlertRegular                   | ⚠️             |
| Hardware/Temp        | TemperatureRegular             | 🌡️             |
| Services             | AppsListRegular                | ⚙️             |
| Network              | WifiRegular                    | 🌐             |

---

## 10. Accessibility

### 10.1 Color Contrast Requirements

```
WCAG 2.1 AA COMPLIANCE
├── Normal text (< 18px):     4.5:1 minimum contrast
├── Large text (≥ 18px):      3:1 minimum contrast
├── UI components:            3:1 minimum contrast
└── Focus indicators:         3:1 minimum contrast

VERIFIED CONTRAST RATIOS
├── #ffffff on #282a36:       14.7:1  ✓
├── #b4b4b4 on #282a36:       7.8:1   ✓
├── #7a7a7a on #282a36:       4.6:1   ✓
├── #0f9d58 on #282a36:       5.2:1   ✓
├── #f4b400 on #282a36:       9.4:1   ✓
└── #db4437 on #282a36:       5.1:1   ✓
```

### 10.2 Focus States

```
KEYBOARD FOCUS INDICATOR
┌─────────────────────────────────────────┐
│                                         │
│   ┌─────────────────────────────────┐   │
│   │   Button Text              ┊    │   │
│   └─────────────────────────────────┘   │
│     ↑                                   │
│     2px solid #60cdff outline           │
│     2px offset (outline-offset)         │
│                                         │
└─────────────────────────────────────────┘

- All interactive elements must show focus
- Tab order must be logical
- Skip links for main content
```

### 10.3 Screen Reader Support

```
ARIA LANDMARKS
├── role="banner"           Header area
├── role="navigation"       Sidebar
├── role="main"             Content area
├── role="complementary"    Status panels
└── role="contentinfo"      Status bar

ARIA LABELS
├── Progress bars:          aria-valuenow, aria-valuemin, aria-valuemax
├── Status indicators:      aria-live="polite" for updates
├── Expandable sections:    aria-expanded
└── Modals:                 aria-modal, aria-labelledby
```

### 10.4 Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}
```

---

## 11. Responsive Behavior

### Breakpoints

```
WINDOW WIDTH ADAPTATIONS
├── < 900px:    Sidebar collapses to icons only (48px)
├── < 1100px:   Cards stack vertically, reduce padding
├── ≥ 1100px:   Full layout as designed
└── ≥ 1600px:   Max-width container (1400px), center content
```

### Collapsed Sidebar

```
┌────────┐
│  📊    │   48px width
├────────┤   Icons only
│  📥    │   Tooltip on hover shows label
├────────┤   Expand button at bottom
│  💾    │
├────────┤
│  🛡️    │
├────────┤
│  ⚙️    │
├────────┤
│   ≫    │   Expand sidebar
└────────┘
```

---

## 12. Implementation Notes

### Component Hierarchy

```
WindowFrame
├── TitleBar (custom or native)
├── MainLayout (horizontal)
│   ├── Sidebar
│   │   ├── Logo
│   │   ├── NavItems[]
│   │   └── FooterActions
│   └── ContentArea
│       ├── Header
│       │   ├── PageTitle
│       │   ├── ActionButtons
│       │   └── HealthScore (on overview)
│       ├── ContentView (switches based on nav)
│       │   ├── OverviewDashboard
│       │   ├── ModuleDetailView
│       │   └── ScanResultsView
│       └── StatusBar
└── ModalContainer (overlay)
    ├── ScanProgressModal
    ├── SettingsModal
    └── ConfirmationDialogs
```

### State Management

```
GlobalState
├── currentView: string
├── healthScore: number
├── lastScanTime: DateTime
├── scanResults: Map<ModuleId, ScanResult>
├── runningScans: Set<ScanId>
└── notifications: Notification[]

ScanResult
├── status: 'healthy' | 'warning' | 'error' | 'unknown'
├── timestamp: DateTime
├── summary: string
├── details: ModuleSpecificData
└── actions: AvailableAction[]
```

---

## 13. File Structure for Implementation

```
/src
├── /components
│   ├── /common
│   │   ├── Button.py
│   │   ├── Card.py
│   │   ├── ProgressBar.py
│   │   ├── StatusChip.py
│   │   └── IconButton.py
│   ├── /layout
│   │   ├── Sidebar.py
│   │   ├── Header.py
│   │   ├── ContentArea.py
│   │   └── StatusBar.py
│   ├── /modules
│   │   ├── OverviewDashboard.py
│   │   ├── WindowsUpdateModule.py
│   │   ├── StorageModule.py
│   │   ├── SecurityModule.py
│   │   └── ... (other modules)
│   └── /modals
│       ├── ScanProgressModal.py
│       └── SettingsModal.py
├── /styles
│   ├── theme.py         (colors, typography tokens)
│   ├── components.py    (styled component definitions)
│   └── animations.py    (animation keyframes)
├── /backend
│   ├── scanners.py      (health check logic)
│   └── system_info.py   (Windows API calls)
└── main.py
```

---

## Summary Comparison

| Aspect              | Minimalist Version          | Depth Version               |
|---------------------|-----------------------------|-----------------------------|
| Cards               | Flat, 1px border            | Subtle shadow, no border    |
| Buttons             | Solid color, no shadow      | Slight elevation on hover   |
| Sidebar             | Flat colored backgrounds    | Subtle gradient backgrounds |
| Modals              | Flat backdrop               | Blurred backdrop            |
| Hover states        | Color change only           | Color + lift (translateY)   |
| Overall feel        | Clean, sharp, utilitarian   | Soft, premium, modern       |

Both versions share the same layout, typography, and spacing — only the surface treatments differ.

---

## 14. Modern UI Enhancements (Implemented)

This section documents the modern UI improvements implemented in `driver_updater_qt_mk5.py` using PyQt6.

### 14.1 Shadow System

The Theme class includes a comprehensive shadow system for creating depth and visual hierarchy.

#### Shadow Constants

```python
SHADOW_BLUR_SM = 8       # Small/subtle shadows
SHADOW_BLUR_MD = 16      # Medium shadows (default for cards)
SHADOW_BLUR_LG = 24      # Large shadows (modals, elevated elements)
SHADOW_COLOR = "#000000"
SHADOW_OPACITY_LIGHT = 40   # Subtle shadow (40/255)
SHADOW_OPACITY_MEDIUM = 80  # Standard shadow (80/255)
SHADOW_OPACITY_HEAVY = 120  # Strong shadow (120/255)
```

#### Shadow Helper Methods

```python
@staticmethod
def apply_shadow(widget, blur_radius=16, offset_x=0, offset_y=4, 
                 color="#000000", opacity=80):
    """Apply a drop shadow effect to any widget."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow_color = QColor(color)
    shadow_color.setAlpha(opacity)
    shadow.setColor(shadow_color)
    shadow.setBlurRadius(blur_radius)
    shadow.setOffset(offset_x, offset_y)
    widget.setGraphicsEffect(shadow)
    return shadow

@staticmethod
def apply_card_shadow(widget):
    """Apply standard card elevation shadow."""
    return Theme.apply_shadow(widget, blur_radius=12, offset_y=3, opacity=60)

@staticmethod
def apply_button_shadow(widget, color="#0078d4"):
    """Apply colored glow shadow for buttons."""
    return Theme.apply_shadow(widget, blur_radius=16, offset_y=2, 
                              color=color, opacity=100)
```

#### Usage Examples

```python
# Standard card shadow
Theme.apply_card_shadow(self)

# Custom shadow with specific parameters
Theme.apply_shadow(self, blur_radius=12, offset_y=3, opacity=60)

# Button glow effect
Theme.apply_button_shadow(button, color="#0078d4")
```

### 14.2 Animation System

#### Animation Timing Constants

```python
ANIM_DURATION_FAST = 150    # Quick micro-interactions
ANIM_DURATION_NORMAL = 250  # Standard transitions
ANIM_DURATION_SLOW = 400    # Deliberate animations
```

#### AnimatedButton Widget

A QPushButton subclass with hover shadow animation for interactive feedback.

```python
class AnimatedButton(QPushButton):
    """Button with animated shadow on hover."""
    
    def __init__(self, text: str = "", variant: str = "primary", parent=None):
        # variant: "primary" (accent blue) or "secondary" (outline)
        
    def enterEvent(self, event):
        # Animates shadow blur from 0 to 20
        
    def leaveEvent(self, event):
        # Animates shadow blur from 20 to 0
```

**Styling:**

```
PRIMARY VARIANT
├── Background: #0078d4 (Windows accent blue)
├── Hover: #1084d8
├── Text: #ffffff
├── Padding: 10px 24px
└── Border radius: 6px

SECONDARY VARIANT
├── Background: transparent
├── Border: 1px solid #5a5a5f
├── Hover background: #38383d
├── Text: #ffffff
└── Border radius: 6px
```

### 14.3 Modern Spinner Widget

A custom spinning arc indicator for loading states, replacing simple text indicators.

```python
class ModernSpinner(QWidget):
    """Modern spinning arc loading indicator."""
    
    def __init__(self, size=32, line_width=3, color="#60cdff", parent=None):
        # size: Diameter of the spinner
        # line_width: Thickness of the arc
        # color: Arc color
```

**Visual Specifications:**

```
SPINNER DESIGN
├── Style: Spinning arc (not full circle)
├── Arc span: 90° (quarter circle)
├── Animation: Continuous rotation at ~60fps
├── Timer interval: 16ms (approximately 60fps)
├── Rotation step: 10° per frame
└── Cap style: Round ends

DEFAULT PARAMETERS
├── Size: 32×32px
├── Line width: 3px
├── Color: #60cdff (accent light blue)
└── Background: Transparent
```

**Usage:**

```python
# Create a spinner
spinner = ModernSpinner(size=24, line_width=2, color="#60cdff")
layout.addWidget(spinner)

# Control visibility
spinner.setVisible(True)   # Start spinning
spinner.setVisible(False)  # Stop (automatically handled)
```

### 14.4 Glow Button Widget

A button with an intensifying glow effect on hover for important actions.

```python
class GlowButton(QPushButton):
    """Button with glow effect that intensifies on hover."""
    
    def __init__(self, text: str = "", glow_color: str = "#0078d4", parent=None):
        # glow_color: The color of the glow effect
```

**Hover Animation:**

```
IDLE STATE
├── Shadow blur: 8px
├── Shadow opacity: 80/255
└── Shadow offset: 0, 2px

HOVER STATE
├── Shadow blur: 24px (animated transition)
├── Shadow opacity: 150/255
└── Animation duration: 150ms
```

### 14.5 Gradient Backgrounds

CSS-style gradients for rich button backgrounds.

#### Gradient Presets

```python
GRADIENT_PRIMARY = "qlineargradient(x1:0, y1:0, x2:1, y2:1, " \
                   "stop:0 #0078d4, stop:1 #00a8e8)"

GRADIENT_SUCCESS = "qlineargradient(x1:0, y1:0, x2:1, y2:1, " \
                   "stop:0 #0f9d58, stop:1 #00c853)"

GRADIENT_ACCENT = "qlineargradient(x1:0, y1:0, x2:0, y2:1, " \
                  "stop:0 #60cdff, stop:1 #0078d4)"
```

#### Button with Gradient Example

```python
# Scan button with gradient background and glow
scan_btn.setStyleSheet(f"""
    QPushButton {{
        background: {Theme.GRADIENT_PRIMARY};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 14px 28px;
        font-size: 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #1084d8, stop:1 #00b4f0);
    }}
    QPushButton:pressed {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #005a9e, stop:1 #0088cc);
    }}
""")
```

### 14.6 Card Shadow Implementation

All major cards include shadow effects for visual elevation.

#### StatusCard Shadow

```python
def _setup_shadow(self):
    """Apply modern shadow effect."""
    Theme.apply_shadow(self, blur_radius=12, offset_y=3, opacity=60)
```

#### HealthSummaryCard Shadow

```python
# Applied in __init__
Theme.apply_shadow(self, blur_radius=16, offset_y=4, opacity=70)
```

#### Other Cards

```python
# StartupProgramsCard, BootSecurityCard, etc.
Theme.apply_card_shadow(self)
```

### 14.7 Visual Effects Summary

| Component          | Effect                  | Parameters                           |
|--------------------|-------------------------|--------------------------------------|
| StatusCard         | Drop shadow             | blur=12, offset_y=3, opacity=60      |
| HealthSummaryCard  | Drop shadow             | blur=16, offset_y=4, opacity=70      |
| StartupProgramsCard| Card shadow (standard)  | blur=12, offset_y=3, opacity=60      |
| BootSecurityCard   | Card shadow (standard)  | blur=12, offset_y=3, opacity=60      |
| Scan Button        | Gradient + Glow         | Primary gradient, glow blur=16       |
| AnimatedButton     | Hover shadow animation  | blur 0→20 on hover                   |
| GlowButton         | Intensifying glow       | blur 8→24 on hover                   |
| ModernSpinner      | Rotating arc            | 90° arc, 60fps rotation              |

### 14.8 Performance Considerations

```
SHADOW EFFECTS
├── Use sparingly on important elements
├── QGraphicsDropShadowEffect can impact performance
├── Consider disabling on lower-end systems
└── Maximum recommended: 5-10 simultaneous shadows

ANIMATIONS
├── Timer-based animations (ModernSpinner) use ~16ms intervals
├── QPropertyAnimation for smooth value transitions
├── Stop animations when widgets are hidden
└── Respect prefers-reduced-motion when possible
```

---

## 15. Modern Table & List Design (Implemented)

This section documents the improved table and list row components for better readability and user-friendliness.

### 15.1 Design Principles

```
READABILITY IMPROVEMENTS
├── Larger row heights (52-60px instead of 40px)
├── Increased padding (16px horizontal, 14px vertical)
├── Larger fonts for primary text (14px instead of 13px)
├── Better color contrast for subtitles
├── Status badges with background colors
└── Alternating row colors for scanning

VISUAL HIERARCHY
├── Category headers with uppercase styling
├── Subtle shadows on list containers
├── Clear visual separation between groups
├── Status icons with consistent sizing (18px)
└── Action buttons with proper hit targets
```

### 15.2 ModernListRow Component

A styled list row with improved readability and hover effects.

```python
class ModernListRow(QFrame):
    """Modern styled list row with improved readability."""
    
    def __init__(self, 
                 title: str = "",
                 subtitle: str = "",
                 status: str = "ok",  # ok, warning, error, info
                 status_text: str = "",
                 is_alternate: bool = False,
                 show_chevron: bool = False,
                 parent=None):
```

**Visual Specifications:**

```
ROW STYLING
├── Height: Auto (typically 52-60px with content)
├── Padding: 16px horizontal, 14px vertical
├── Spacing: 14px between elements
├── Background (normal): #2d2d32 
├── Background (alternate): #292930 (slightly darker)
├── Hover: #38383d
└── Border: None (container handles borders)

TITLE TEXT
├── Font size: 14px
├── Font weight: 500 (Medium)
├── Color: #ffffff (TEXT_PRIMARY)
└── Line height: 20px

SUBTITLE TEXT
├── Font size: 12px
├── Font weight: 400 (Regular)
├── Color: #7a7a7a (TEXT_TERTIARY)
└── Line height: 18px

STATUS BADGE
├── Font size: 11px
├── Font weight: 600 (SemiBold)
├── Padding: 4px 10px
├── Border radius: 4px
├── Background: Color-specific (see below)

STATUS BADGE COLORS
├── OK:      Background: rgba(15,157,88,0.15)  Text: #0f9d58
├── Warning: Background: rgba(244,180,0,0.15)  Text: #f4b400
├── Error:   Background: rgba(219,68,55,0.15)  Text: #db4437
└── Info:    Background: rgba(66,133,244,0.15) Text: #60cdff
```

### 15.3 ModernCategoryHeader Component

A styled category header for grouping list items.

```python
class ModernCategoryHeader(QFrame):
    """Category header for grouping list items."""
    
    def __init__(self, title: str, count: int = 0, parent=None):
```

**Visual Specifications:**

```
HEADER STYLING
├── Height: Fixed 40px
├── Padding: 16px horizontal
├── Background: #232328 (BG_SIDEBAR)
├── Border-bottom: 1px solid #3a3a3f
└── Text transform: UPPERCASE

TITLE TEXT
├── Font size: 11px
├── Font weight: 700 (Bold)
├── Color: #b4b4b4 (TEXT_SECONDARY)
├── Letter spacing: 1px
└── Text transform: uppercase

COUNT BADGE
├── Font size: 11px
├── Font weight: 600
├── Color: #7a7a7a (TEXT_TERTIARY)
└── Format: "(count)"
```

### 15.4 ModernListContainer Component

A container that manages list items with proper styling.

```python
class ModernListContainer(QFrame):
    """Container for modern list items."""
    
    def add_category(self, title: str, count: int = 0) -> ModernCategoryHeader
    def add_row(self, title, subtitle, status, status_text, show_chevron) -> ModernListRow
    def add_separator(self)
    def add_more_label(self, text: str)
    def clear(self)
```

**Visual Specifications:**

```
CONTAINER STYLING
├── Background: #2d2d32 (BG_CARD)
├── Border: 1px solid #3a3a3f
├── Border radius: 8px
├── Shadow: blur=12, offset_y=3, opacity=50
└── Overflow: Hidden (for rounded corners)

SPACING
├── No margins between items
├── No spacing between items (0px)
└── Dividers handled by category headers
```

### 15.5 Improved Stats Display

Enhanced statistics display with visual dividers and color coding.

```
STAT BOX STYLING
├── Min width: 100px
├── Value font size: 24px (up from 18px)
├── Value font weight: 700
├── Label font size: 11px
├── Label text transform: uppercase
├── Label letter spacing: 0.5px
├── Color coding by type (success/warning/error)

STAT DIVIDERS
├── Width: 1px
├── Height: 40px
├── Color: #3a3a3f
├── Margin: 24px horizontal
```

### 15.6 Usage Examples

**Driver Manager Page:**

```python
# Create modern list container
self.drivers_list = ModernListContainer()

# Add category with count
self.drivers_list.add_category("Audio Endpoint", 6)

# Add rows with full styling
row = self.drivers_list.add_row(
    title="Realtek Audio Effects",
    subtitle="Realtek • v13.0.6000.1167 • 2024-01-23",
    status="ok",
    status_text="OK"
)

# Add action button to row
row.add_action_button("Fix", callback, primary=True)

# Add "more items" label
self.drivers_list.add_more_label("... and 3 more drivers")
```

### 15.7 Comparison: Before vs After

| Aspect              | Before                    | After                     |
|---------------------|---------------------------|---------------------------|
| Row Height          | ~40px                     | ~56px                     |
| Padding             | 10px 16px                 | 14px 16px                 |
| Title Font          | 13px                      | 14px Medium               |
| Subtitle Font       | 11px                      | 12px                      |
| Status Display      | Plain text                | Colored badge with bg     |
| Alternating Rows    | No                        | Yes (subtle)              |
| Category Headers    | Plain label               | Uppercase styled header   |
| Container Shadow    | None                      | Subtle drop shadow        |
| Icon Size           | 16px                      | 18px                      |
| Action Buttons      | Inline small              | Proper sized, styled      |

---

*This specification provides a complete blueprint for building a professional Windows Health Checker application that feels cohesive, intentional, and premium.*
