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
│   (184px)    │                                                              │
│              │  CONTENT AREA                                                │
│  ┌────────┐  │                                                              │
│  │Overview│  │  ┌─────────────────────────────────────────────────────────┐ │
│  ├────────┤  │  │                                                         │ │
│  │Drivers │  │  │  Module content renders here based on                   │ │
│  ├────────┤  │  │  sidebar selection                                      │ │
│  │Startup │  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Updates │  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Storage │  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Security│  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Software│  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Hardware│  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │System  │  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Events  │  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Audio   │  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Tools   │  │  │                                                         │ │
│  ├────────┤  │  │                                                         │ │
│  │Settings│  │  │                                                         │ │
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

### Semantic Colors (Optimized for User Comfort)

Colors are slightly desaturated from pure Material/Apple colors to reduce visual fatigue on dark backgrounds while maintaining clear status communication.

| Status | Color | Hex | Background Overlay | Notes |
|--------|-------|-----|-------------------|-------|
| Success | Soft Green | `#34c759` | `rgba(74,222,128,0.12)` | Calming, not neon |
| Warning | Warm Amber | `#f5c542` | `rgba(251,191,36,0.12)` | Warmer than pure yellow |
| Error | Soft Red | `#e85d5d` | `rgba(248,113,113,0.12)` | Noticeable but not alarming |
| Info | Soft Blue | `#5a9fff` | `rgba(96,165,250,0.12)` | Calm, informative |
| Running | Soft Purple | `#a855f7` | `rgba(167,139,250,0.12)` | Engaging but not distracting |

> **Design Philosophy:** Bright, saturated status colors can cause visual fatigue and unnecessary anxiety (especially red). These softer alternatives maintain clear communication while being easier on the eyes during extended use.

### Text Hierarchy (Improved Contrast)

| Level | Hex | Usage |
|-------|-----|-------|
| Primary | `#ffffff` | Headings, important labels |
| Secondary | `#b8b8c0` | Body text, card subtitles |
| Tertiary | `#909098` | Captions, timestamps |
| Disabled | `#686870` | Inactive elements |

### Borders

```txt
BORDER        = #404048    (Visible border)
BORDER_LIGHT  = #505058    (Emphasis)
BORDER_ACCENT = #0078d4    (Windows blue for focus states)
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
Icons:        "Segoe Fluent Icons", "Segoe MDL2 Assets"
```

### Iconography - Segoe Fluent Icons

All icons in the application use **Segoe Fluent Icons** - the native Windows 11 icon font. This ensures:
- Consistent visual language with Windows 11
- Crisp rendering at any size
- Automatic theme color inheritance
- No external icon assets needed

#### Icon Reference Table

| Name       | Unicode  | Usage                          |
|------------|----------|--------------------------------|
| grid       | `\uE80A` | Overview/Dashboard             |
| download   | `\uE896` | Drivers/Downloads              |
| hdd        | `\uEDA2` | Storage                        |
| shield     | `\uE83D` | Security                       |
| cpu        | `\uE950` | Hardware/Processor             |
| file       | `\uE8A5` | System/Documents               |
| alert      | `\uE7BA` | Events/Warnings                |
| gear       | `\uE713` | Settings                       |
| chip       | `\uE964` | Memory/Hardware                |
| rocket     | `\uE7C4` | Startup/Launch                 |
| speaker    | `\uE767` | Audio                          |
| wrench     | `\uE90F` | Tools/Repair                   |
| package    | `\uE7B8` | Software/Apps                  |
| update     | `\uE895` | Windows Update                 |
| defender   | `\uE83D` | Windows Defender               |
| storage    | `\uE8B7` | Storage/Disk                   |
| health     | `\uE8C9` | Drive Health                   |
| memory     | `\uE964` | Memory/RAM                     |
| events     | `\uE7BA` | Event Logs                     |
| play       | `\uE768` | Startup Programs               |
| lock       | `\uE72E` | Boot Security                  |
| timer      | `\uE916` | System Info/Uptime             |
| task       | `\uE9D5` | Task Manager                   |
| device     | `\uE772` | Device Manager                 |
| broom      | `\uE90F` | Disk Cleanup                   |

#### Implementation

```python
class NavIcon(QWidget):
    """Navigation icon using Segoe Fluent Icons"""
    
    FLUENT_ICONS = {
        "grid": "\uE80A",
        "download": "\uE896",
        "shield": "\uE83D",
        # ... etc
    }
    
    def _update_icon(self):
        icon_char = self.FLUENT_ICONS.get(self.icon_name, "\uE946")
        self.icon_label.setStyleSheet(f"""
            background: transparent;
            color: {self.color};
            font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
            font-size: {self.icon_size}px;
        """)
```

#### Icon Sizing Guidelines

| Context           | Size    | Notes                              |
|-------------------|---------|------------------------------------|
| Sidebar Nav       | 20px    | Standard navigation icons          |
| Card Headers      | 14-16px | Compact card title icons           |
| Quick Tools       | 18px    | Action button icons                |
| Status Indicators | 12px    | Small inline status icons          |

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
│  Border-radius: 0px (straight edges)│
│  Margin: 0px (full-width highlight) │
└─────────────────────────────────────┘

SIDEBAR DESIGN PRINCIPLES:
- Full-width highlight: Selected item highlight spans entire sidebar width
- No margins: Sidebar items have no left/right margins
- Straight edges: No rounded corners on sidebar items (border-radius: 0px)
- Sidebar width sized to content: 184px matches text content without excess space
```

#### Sidebar Navigation Grouping

To improve navigation clarity, sidebar items are organized into logical groups with subtle visual separators.

```
NAVIGATION GROUPS:

┌──────────────────────────┐
│  📊  Overview            │  ← Dashboard (standalone)
├──────────────────────────┤
│                          │  ← Subtle divider (8px space + 1px line)
│  SYSTEM HEALTH           │  ← Group label (optional)
│  🔧  Drivers             │
│  🚀  Startup             │
│  📥  Updates             │
│  💾  Storage             │
│  🛡️  Security            │
├──────────────────────────┤
│                          │
│  SYSTEM INFO             │
│  📦  Software            │
│  🖥️  Hardware            │
│  📄  System              │
│  ⚠️  Events              │
│  🔊  Audio               │
├──────────────────────────┤
│                          │
│  🛠️  Tools               │  ← Utilities (standalone)
├──────────────────────────┤
│  ⚙️  Settings            │  ← Settings (always at bottom)
└──────────────────────────┘

GROUP SPECIFICATIONS:
- Group label (optional): 10px, uppercase, #7a7a7a, letter-spacing 1px
- Divider: 1px solid #3a3a3f
- Spacing above divider: 8px
- Spacing below divider: 8px
- Group label padding: 12px 16px 4px 16px

GROUP DEFINITIONS:
├── Dashboard:     Overview (home/summary page)
├── System Health: Drivers, Startup, Updates, Storage, Security
│                  (items that check for issues and can be "fixed")
├── System Info:   Software, Hardware, System, Events, Audio
│                  (informational pages, less actionable)
├── Utilities:     Tools (Windows tools launcher)
└── Settings:      App settings (always bottom, separated)

VISUAL DISTINCTION:
- Groups help users understand what each section does
- "System Health" items typically show status indicators
- "System Info" items are more informational
- Separators create visual breathing room in long list
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

### 5.4 Quick Status Card (Dashboard Grid)

Compact status cards displayed in a 3×2 grid on the Overview dashboard.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ✓   Windows Update                                    >   │
│       Up to date                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

SPECIFICATIONS:
- Width: Flexible, typically 1/3 of content area (3 per row)
- Height: 80-90px (auto-expand for longer content)
- Min-height: 80px
- Padding: 16px
- Border radius: 8px
- Background: #2d2d32 (BG_CARD)
- Hover background: #38383d (BG_CARD_HOVER)
- Border: 1px solid transparent (default)
- Border on error/warning: 1px solid status color at 30% opacity
- Clickable: Yes (navigates to detail module)
- Cursor: pointer

ADAPTIVE SIZING (Content-aware):
- Cards in the same row should align to the tallest card's height
- Use CSS Grid with `grid-auto-rows: minmax(80px, auto)` or Flexbox with `align-items: stretch`
- Subtitle text wraps to 2 lines maximum before truncation
- For cards with longer content (e.g., "0 critical, 22 errors"):
  ├── Allow natural height expansion
  ├── Keep consistent padding
  └── Row alignment ensures visual harmony

CONTENT PRIORITY:
- If subtitle is too long, truncate with ellipsis
- Tooltip shows full text on hover for truncated content
- Status badge takes priority over subtitle space
```

#### Status Icon Positioning (CRITICAL - Consistency Rule)

```
LAYOUT STRUCTURE:
┌─────────────────────────────────────────────────────────────┐
│  [STATUS_ICON]  [CONTENT]                        [CHEVRON]  │
│      24px        flex-1                            16px     │
└─────────────────────────────────────────────────────────────┘

STATUS ICON (Left side, ALWAYS visible):
- Position: Left side, vertically centered
- Size: 24×24px container, 18px icon
- Margin right: 14px
- Icons by status:
  ├── OK:      ✓ (checkmark) in #0f9d58 (green)
  ├── Warning: ⚠ (triangle) in #f4b400 (amber)  
  ├── Error:   ✗ (x mark) in #db4437 (red)
  └── Info:    ℹ (info) in #60cdff (blue)

CONTENT (Center):
- Title: 14px, SemiBold, #ffffff (TEXT_PRIMARY)
- Subtitle: 12px, Regular, #9e9e9e (TEXT_SECONDARY)
- Line height: Title 20px, Subtitle 18px
- Max lines: Title 1 (ellipsis), Subtitle 1 (ellipsis)

CHEVRON (Right side):
- Icon: > (right arrow) 
- Size: 16px
- Color: #636363 (disabled/hint)
- Hover color: #9e9e9e
- Indicates clickability
```

#### Status-Specific Card Styling

```
OK STATUS:
├── Background: #2d2d32
├── Border: 1px solid transparent
├── Icon: ✓ in #0f9d58
└── No additional styling

WARNING STATUS:
├── Background: #2d2d32
├── Border: 1px solid rgba(244,180,0,0.3)
├── Icon: ⚠ in #f4b400
└── Subtle amber tint on hover

ERROR STATUS:
├── Background: #2d2d32  
├── Border: 1px solid rgba(219,68,55,0.3)
├── Icon: ✗ in #db4437
└── Subtle red tint on hover
```

#### Accessibility Requirements

```
- ARIA role: "button" (since clickable)
- ARIA label: "{title}: {subtitle}. Status: {status}. Click to view details."
- Focus visible: 2px solid #60cdff outline
- Tab order: Left-to-right, top-to-bottom in grid
- Keyboard: Enter/Space to activate
```

### 5.5 Tip Banner Component

A rotating informational banner displayed at the top of the Overview dashboard.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   🔔  TIP   Review App Permissions                           ● ● ● ○ ○     │
│             Periodically check which apps have access to                    │
│             your camera, microphone, and location.                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

SPECIFICATIONS:
- Width: 100% of content area
- Height: Auto (typically 80-100px)
- Padding: 20px
- Border radius: 8px
- Background: #2d2d32 (BG_CARD)
- Border: 1px solid #3a3a3f
```

#### Layout Structure

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [ICON]  [BADGE]  [CONTENT]                              [PAGINATION]    │
│   24px    auto     flex-1                                   auto         │
└──────────────────────────────────────────────────────────────────────────┘

ICON:
- Size: 24×24px
- Type: Contextual (lightbulb 💡, bell 🔔, shield 🛡️, etc.)
- Color: #f4b400 (amber) for tips, varies by type
- Margin right: 12px

BADGE:
- Text: "TIP" or "INFO" or "SECURITY"
- Font: 10px, Bold, uppercase
- Background: rgba(244,180,0,0.2) for tips
- Text color: #f4b400
- Padding: 2px 8px
- Border radius: 4px
- Margin right: 12px

CONTENT:
- Title: 14px, SemiBold, #ffffff
- Description: 13px, Regular, #9e9e9e
- Max lines: Title 1, Description 2

PAGINATION DOTS:
- Dot size: 6px diameter
- Active dot: #ffffff
- Inactive dot: #636363
- Spacing: 8px between dots
- Shows current position in rotation
```

#### Rotation Behavior

```
AUTO-ROTATE:
- Interval: 8 seconds between tips
- Animation: Fade out (200ms) → Fade in (200ms)
- Pause on hover: Yes
- Resume after hover: Yes (restart timer)

MANUAL NAVIGATION:
- Click pagination dot: Jump to that tip
- Swipe (touch): Previous/next tip
- Keyboard: Arrow left/right when focused

TIP CONTENT EXAMPLES:
├── "Review App Permissions" - Privacy check
├── "Clear Browser Cache" - Performance tip  
├── "Check Startup Programs" - Boot optimization
├── "Update Your Drivers" - Hardware maintenance
└── "Run Disk Cleanup" - Storage management
```

### 5.6 Quick Tools Panel (Right Sidebar)

A floating vertical toolbar providing quick access to common actions.

```
┌──────┐
│  ☰   │   View toggle (list/grid)
├──────┤
│  ⊞   │   QR code / Share
├──────┤
│  🔧  │   Quick settings
├──────┤
│  ↻   │   Refresh / Re-scan
└──────┘

SPECIFICATIONS:
- Width: 48px
- Position: Fixed, right side of content area
- Top offset: Aligned with content top + 200px
- Background: #2d2d32 (BG_CARD)
- Border: 1px solid #3a3a3f
- Border radius: 8px
- Shadow: blur=8, offset_y=2, opacity=60
```

#### Button Specifications

```
ICON BUTTON:
- Size: 40×40px (with 4px margin = 48px container)
- Icon size: 18px
- Icon color: #9e9e9e (default)
- Hover icon color: #ffffff
- Background: transparent (default)
- Hover background: #38383d
- Border radius: 6px
- Cursor: pointer

TOOLTIP (REQUIRED):
- Position: Left of button
- Delay: 500ms before showing
- Background: #1e1e1e
- Text: 12px, #ffffff
- Padding: 6px 10px
- Border radius: 4px
- Shadow: blur=8, opacity=80
```

#### Button Definitions

| Position | Icon | Tooltip | Action |
|----------|------|---------|--------|
| 1 | ☰ (list) | "Toggle View" | Switch between list/grid view |
| 2 | ⊞ (QR) | "System Report" | Generate shareable system report |
| 3 | 🔧 (wrench) | "Quick Settings" | Open settings panel |
| 4 | ↻ (refresh) | "Refresh All" | Re-run all health checks |

#### Collapsed State

```
When content area width < 1000px:
- Panel collapses to single toggle button
- Click expands to show all buttons
- Click outside collapses
```

### 5.7 Health Score Ring

A circular progress indicator displaying the overall system health score.

```
        ╭─────────────╮
       ╱    ░░░░░░░    ╲
      │   ███████░░░    │
      │                 │
      │       65        │
      │                 │
      │   ███████░░░    │
       ╲    ░░░░░░░    ╱
        ╰─────────────╯

SPECIFICATIONS:
- Outer diameter: 160px
- Ring thickness: 12px
- Inner diameter: 136px (160 - 12*2)
- Background track: #38383d at 30% opacity
```

#### Ring Gradient Colors by Score

```
SCORE 80-100 (Healthy):
├── Start: #0f9d58 (green)
├── End: #00c853 (bright green)
└── Direction: Clockwise from top

SCORE 60-79 (Attention Needed):
├── Start: #f4b400 (amber)
├── End: #ffcc00 (yellow)
└── Direction: Clockwise from top

SCORE 0-59 (Critical):
├── Start: #db4437 (red)
├── End: #ff6b6b (light red)
└── Direction: Clockwise from top
```

#### Center Content

```
SCORE NUMBER:
- Font: 48px, Bold
- Color: #ffffff
- Position: Centered vertically and horizontally

SUBTEXT (Optional):
- Text: "/ 100" or status label
- Font: 14px, Regular
- Color: #9e9e9e
- Position: Below score number
```

#### Animation

```
ON LOAD / SCORE CHANGE:
- Animation: Ring fills from 0% to target %
- Duration: 800ms
- Easing: ease-out
- Score number: Counts up from 0 to target

PULSE (Optional for low scores):
- Subtle pulse animation for scores < 50
- Scale: 1.0 → 1.02 → 1.0
- Duration: 2s, infinite
```

### 5.8 Startup Programs Card

A compact card showing startup program statistics with warning badge.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ▶   Startup Programs                    ⚠ Warning         │
│       61 enabled, 6 disabled                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘

SPECIFICATIONS:
- Width: ~50% of content area
- Height: 80px
- Padding: 16px 20px
- Border radius: 8px
- Background: #2d2d32
- Clickable: Yes
```

#### Warning Thresholds

```
STATUS CALCULATION:
├── OK (no badge):     enabled ≤ 30
├── Warning:           enabled 31-60  
├── Attention:         enabled > 60
└── Critical:          enabled > 100 or known problematic apps

WARNING BADGE:
- Text: "Warning" or "Attention"
- Font: 11px, SemiBold
- Background: rgba(244,180,0,0.2)
- Text color: #f4b400
- Padding: 4px 10px
- Border radius: 4px
- Position: Right side, vertically centered
```

#### Content Layout

```
[ICON]  [TITLE + BADGE]      
        [SUBTITLE]           

ICON:
- Character: ▶ (play symbol) or 🚀
- Size: 20px
- Color: #60cdff

TITLE:
- Text: "Startup Programs"
- Font: 14px, SemiBold, #ffffff

SUBTITLE:
- Format: "{enabled} enabled, {disabled} disabled"
- Font: 12px, Regular, #9e9e9e
```

### 5.9 Boot Security Card

A compact card showing secure boot and TPM status.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   🔒  Boot Security                                         │
│                                                             │
│       Secure Boot              Enabled  ●                   │
│       TPM 2.0                  Active   ●                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

SPECIFICATIONS:
- Width: ~50% of content area
- Height: Auto (typically 100-120px)
- Padding: 16px 20px
- Border radius: 8px
- Background: #2d2d32
```

#### Status Row Layout

```
[LABEL]                              [STATUS]  [DOT]

LABEL:
- Font: 13px, Regular, #9e9e9e
- Examples: "Secure Boot", "TPM 2.0", "UEFI Mode"

STATUS TEXT:
- Font: 13px, SemiBold
- Color: Status-specific (green/amber/red)
- Values: "Enabled", "Disabled", "Active", "Not Found"

STATUS DOT:
- Size: 8px diameter
- Color: Matches status (green/amber/red)
- Margin left: 8px
```

#### Status Colors

```
ENABLED/ACTIVE:
├── Text: #0f9d58 (green)
└── Dot: #0f9d58

DISABLED:
├── Text: #f4b400 (amber) 
└── Dot: #f4b400

NOT FOUND/ERROR:
├── Text: #db4437 (red)
└── Dot: #db4437
```

### 5.10 Progress Indicators

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

### 5.11 Buttons

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

#### Status Bar vs. Main Content (Avoiding Duplication)

```
RULE: Status information should appear in ONE location based on context.

DURING SCAN:
├── Main content: Shows detailed progress modal or inline progress
├── Status bar: Shows "Scanning... 3/7 checks complete"
└── Health summary: Hidden or shows "Scanning..."

AFTER SCAN (Overview page):
├── Main content: Shows health score ring with summary text
│   └── "4 checks passed • 1 warning • 2 errors"
├── Status bar: Shows timestamp only
│   └── "Scan complete - Today 2:45 PM"
└── Do NOT duplicate counts in both locations

ON MODULE PAGES:
├── Main content: Module-specific status
├── Status bar: "Ready" or module-specific message
└── No health score summary in status bar
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

## 7. Page Structure & Navigation Hierarchy

This section defines the rules for page titles, headers, sub-pages, and navigation patterns throughout the application.

### 7.0 Page Hierarchy Overview

```
NAVIGATION LEVELS:

Level 1: MAIN PAGES (Sidebar Navigation)
├── Accessed via sidebar click
├── Each is a distinct functional area
├── Title displayed at top of content area
├── Examples: Overview, Drivers, Startup, Updates, Storage, Security, etc.

Level 2: SUB-PAGES / TABS (Horizontal Tab Bar)
├── Accessed via tab buttons within a main page
├── Organizes related content within a page
├── Tabs appear below page title
├── Examples: "Installed Drivers" | "Driver Cleanup" | "Updates & Resources"

Level 3: SECTIONS (Within Page/Tab Content)
├── Visual groupings within content
├── Section headers with optional expand/collapse
├── Examples: "Safe to Remove", "System Health", "Quick Status"

Level 4: ITEMS (List Rows, Cards)
├── Individual data items
├── May expand to show details or trigger modals
└── Examples: Driver row, startup program row, storage drive card
```

### 7.0.1 Page Title Specifications

```
MAIN PAGE TITLE (Level 1):
├── Font size: 28px
├── Font weight: 600 (SemiBold)
├── Color: Theme.TEXT_PRIMARY (#ffffff)
├── Position: Top-left of content area
├── Margin: 32px left, 28px top
├── Line height: 36px
├── Letter spacing: -0.5px

TITLE ROW LAYOUT:
┌────────────────────────────────────────────────────────────────────────┐
│ Page Title                                        [Primary Action Btn] │
│ (28px, SemiBold)                                  (e.g., "Open Device  │
│                                                    Manager", "Run Scan")│
└────────────────────────────────────────────────────────────────────────┘

TITLE NAMING CONVENTIONS:
├── Use noun phrases: "Driver Manager", "Storage Health", "System Events"
├── Keep concise: 1-3 words maximum
├── Match sidebar label when possible
├── Avoid verbs: "Manage Drivers" ❌ → "Driver Manager" ✓
└── Title case: Capitalize each word
```

### 7.0.2 Tab Navigation (Sub-Pages)

```
TAB BAR SPECIFICATIONS:
├── Position: Below page title, above content
├── Height: 44px
├── Spacing between tabs: 0px (tabs touch)
├── Background: Transparent
├── Margin bottom: 20px

TAB BUTTON STYLING:

INACTIVE TAB:
├── Background: Transparent
├── Text color: Theme.TEXT_SECONDARY
├── Font size: 14px
├── Font weight: 500
├── Padding: 12px 24px
├── Border: None
├── Border-bottom: 2px solid transparent

ACTIVE TAB:
├── Background: Theme.BG_CARD or subtle highlight
├── Text color: Theme.TEXT_PRIMARY
├── Font weight: 600
├── Border-bottom: 2px solid Theme.ACCENT
├── Border-radius: 8px 8px 0 0 (top corners only)

HOVER TAB (inactive):
├── Background: Theme.BG_CARD_HOVER
├── Text color: Theme.TEXT_PRIMARY

TAB CONTENT TRANSITIONS:
├── Use AnimatedStackedWidget for smooth transitions
├── Duration: 150ms (faster than page transitions)
├── Direction: Slide left/right based on tab position
└── Fade: Subtle opacity transition

TAB NAMING CONVENTIONS:
├── Use descriptive labels: "Installed Drivers", "Driver Cleanup"
├── Keep labels short: 2-3 words maximum
├── Use "&" for compound labels: "Updates & Resources"
├── Indicate counts if relevant: "Warnings (3)"
└── Avoid icons in tab labels (text only)
```

### 7.0.3 Section Headers

```
SECTION HEADER (Level 3):
├── Font size: 16px
├── Font weight: 600 (SemiBold)
├── Color: Theme.TEXT_PRIMARY
├── Margin top: 24px (space from previous section)
├── Margin bottom: 12px (space before content)
├── Optional count badge: "(22)" in Theme.TEXT_SECONDARY

COLORED SECTION HEADERS (for status-grouped content):
├── Success sections: Color Theme.SUCCESS (green)
│   Example: "Safe to Remove (22)"
├── Warning sections: Color Theme.WARNING (amber)
│   Example: "Use Caution (5)"
├── Error sections: Color Theme.ERROR (red)
│   Example: "Critical Issues (3)"

SECTION HEADER WITH COUNT:
┌────────────────────────────────────────────────────────────────────────┐
│ Section Title (count)                            [Optional Action Btn] │
│ "Safe to Remove (22)"                                      [Remove All]│
└────────────────────────────────────────────────────────────────────────┘

COLLAPSIBLE SECTIONS:
├── Chevron icon: Right-pointing (▶) when collapsed, down (▼) when expanded
├── Click header row to toggle
├── Animate height: 200ms ease-out
├── Remember state: Persist user's expand/collapse preference
└── Default state: Expanded (show content)
```

### 7.0.4 Navigation State Management

```
NAVIGATION STATE RULES:

1. SIDEBAR SELECTION:
   ├── Exactly one sidebar item selected at all times
   ├── Selection persists until user clicks different item
   ├── Clicking same item does nothing (no refresh)
   └── Active state: Blue accent background with left border

2. TAB SELECTION (within page):
   ├── Exactly one tab selected when tabs are present
   ├── Default to first tab on page load
   ├── Remember last selected tab when returning to page
   └── Tab state is per-page (not global)

3. DEEP LINKING / NAVIGATION SIGNALS:
   ├── Cards on Overview can navigate to specific pages
   ├── Emit signal with target page ID: card_clicked.emit("drivers")
   ├── MainWindow handles navigation and tab selection
   └── Optional: Navigate to specific tab: "drivers:cleanup"

4. BACK NAVIGATION:
   ├── No explicit back button (use sidebar to navigate)
   ├── Tabs don't have back (switch tabs or use sidebar)
   ├── Modals have close button (X) or Cancel
   └── Dialogs: Escape key or Cancel button

NAVIGATION URL PATTERN (for internal linking):
├── page_id                    → Navigate to page, default tab
├── page_id:tab_id             → Navigate to page, specific tab
└── page_id:tab_id:section_id  → Navigate to page, tab, scroll to section
```

### 7.0.5 Page Layout Template

```
STANDARD PAGE STRUCTURE:

┌────────────────────────────────────────────────────────────────────────┐
│ MARGINS: 32px left/right, 28px top/bottom                              │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│ Page Title (28px)                              [Primary Action Button] │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│ [Tab 1] [Tab 2] [Tab 3]                        (if page has tabs)      │
│ ────────────────────────                                               │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│ SCROLLABLE CONTENT AREA                                                │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │                                                                    │ │
│ │  Info Banner (optional - tips, warnings)                           │ │
│ │                                                                    │ │
│ │  Section Header                                                    │ │
│ │  ┌──────────────────────────────────────────────────────────────┐ │ │
│ │  │ Content Card / List Container                                │ │ │
│ │  │ - Row 1                                                      │ │ │
│ │  │ - Row 2                                                      │ │ │
│ │  │ - Row 3                                                      │ │ │
│ │  └──────────────────────────────────────────────────────────────┘ │ │
│ │                                                                    │ │
│ │  Section Header 2                                                  │ │
│ │  ┌──────────────────────────────────────────────────────────────┐ │ │
│ │  │ Content Card / List Container                                │ │ │
│ │  └──────────────────────────────────────────────────────────────┘ │ │
│ │                                                                    │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘

SPACING RULES:
├── Page title to tabs: 20px
├── Tabs to content: 20px
├── Between sections: 24px
├── Section header to content: 12px
├── Between cards/containers: 16px
└── Content padding inside scroll area: 0 (handled by cards)
```

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

### Emoji Exception: Windows Tools Page

**The Windows Tools page is permitted to use emojis** for category icons in the navigation menu.
This exception exists because:
- The Tools page contains 20+ categories of Windows settings and system tools
- Emojis provide instant visual recognition for each category type
- The colorful emojis help differentiate between Settings vs System Tools sections
- Users can quickly scan and find the category they need

Approved emojis for Windows Tools categories:
| Category         | Emoji | Description           |
|------------------|-------|-----------------------|
| System           | 🖥️    | Display, sound, power |
| Network          | 🌐    | Wi-Fi, ethernet, VPN  |
| Personalize      | 🎨    | Themes, colors        |
| Apps             | 📦    | Installed apps        |
| Accounts         | 👤    | Users, sign-in        |
| Time & Language  | 🕐    | Date, region          |
| Gaming           | 🎮    | Game bar, captures    |
| Accessibility    | ♿    | Vision, hearing       |
| Privacy          | 🔒    | Security, permissions |
| Windows Update   | 🔄    | Updates, recovery     |
| Core Tools       | ⚙️    | Control Panel, etc    |
| Admin Tools      | 🛠️    | Task Manager, etc     |
| Security Tools   | 🛡️    | Firewall, credentials |
| Network Tools    | 📡    | Network adapters      |
| Disk Tools       | 💾    | Cleanup, defrag       |
| Display Tools    | 🖼️    | Resolution, DirectX   |
| Device Tools     | 🔊    | Sound, printers       |
| Power Tools      | 🔋    | Power options         |
| Developer Tools  | 💻    | Terminal, env vars    |
| Recovery Tools   | 🔧    | Troubleshoot, restore |

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

### 10.5 Keyboard Navigation

```
GLOBAL NAVIGATION:
├── Tab: Move focus to next interactive element
├── Shift+Tab: Move focus to previous element
├── F6: Cycle between major regions (sidebar, content, toolbar)
└── Escape: Close modals, cancel operations

SIDEBAR NAVIGATION:
├── Arrow Up/Down: Move between nav items
├── Enter/Space: Select nav item
├── Home: Jump to first item (Overview)
└── End: Jump to last item (Settings)

QUICK STATUS CARDS (Grid):
├── Arrow keys: Navigate between cards
│   ├── Left/Right: Previous/next in row
│   └── Up/Down: Same position in adjacent row
├── Enter/Space: Activate card (navigate to module)
├── Tab: Move to next card (left-to-right, top-to-bottom)
└── Focus order: Row 1 (L→R), Row 2 (L→R)

QUICK TOOLS PANEL:
├── Arrow Up/Down: Navigate between tool buttons
├── Enter/Space: Activate tool
└── Escape: Return focus to main content

TIP BANNER:
├── Arrow Left/Right: Previous/next tip
├── Enter: Activate tip action (if any)
└── Tab: Skip banner, move to next element

MODALS:
├── Tab: Cycle through modal controls
├── Escape: Close modal
├── Enter: Activate focused button
└── Focus trap: Tab stays within modal
```

### 10.6 Tooltips Specification

```
TOOLTIP BEHAVIOR:
├── Trigger: Hover (mouse) or Focus (keyboard)
├── Delay before show: 500ms
├── Delay before hide: 200ms
├── Position: Prefer left of element, fallback to top
└── Pointer events: None (don't block interaction)

TOOLTIP STYLING:
├── Background: #1e1e1e
├── Border: 1px solid #3a3a3f
├── Text: 12px, Regular, #ffffff
├── Padding: 6px 10px
├── Border radius: 4px
├── Shadow: blur=8, offset_y=2, opacity=60
├── Max width: 200px
└── Word wrap: Yes

REQUIRED TOOLTIPS:
├── Quick Tools panel buttons (always)
├── Icon-only buttons (always)
├── Truncated text (on overflow)
├── Status icons (explain meaning)
└── Health score ("What does this mean?")

TOOLTIP CONTENT EXAMPLES:
├── List icon: "Toggle between list and grid view"
├── QR icon: "Generate system report to share"
├── Wrench icon: "Open quick settings"
├── Refresh icon: "Re-run all health checks"
└── Health score: "Score based on 12 system checks. 80+ is healthy."
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

## 12. Empty States & Edge Cases

Define how the UI handles missing data, errors, and first-run scenarios.

### 12.1 First Run (Never Scanned)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   System Health Score                                                   │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                                                                 │   │
│   │        ╭─────────────╮                                          │   │
│   │       ╱               ╲      --                                 │   │
│   │      │    ░░░░░░░░    │      Run your first scan                │   │
│   │      │    ░░░░░░░░    │                                         │   │
│   │       ╲    ░░░░░░░   ╱       No health data yet                 │   │
│   │        ╰─────────────╯                                          │   │
│   │                                                                 │   │
│   │   [Run Full Scan]                                               │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   Quick Status                                                          │
│   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐          │
│   │ ?  Windows Update│ │ ?  Defender     │ │ ?  Storage      │          │
│   │   Not checked    │ │   Not checked   │ │   Not checked   │          │
│   └─────────────────┘ └─────────────────┘ └─────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘

SPECIFICATIONS:
- Score display: "--" instead of number
- Ring: Empty (gray track only, no fill)
- Status text: "Run your first scan" / "No health data yet"
- Quick Status cards: "?" icon, "Not checked" subtitle
- CTA: Prominent "Run Full Scan" button
```

### 12.2 Scan Error / Data Fetch Failed

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ✗   Windows Update                            ⚠ Error     │
│       Could not connect to update service                   │
│                                                             │
│       [Retry]  [Troubleshoot]                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘

ERROR CARD SPECIFICATIONS:
- Icon: ✗ or ⚠ in #db4437 (red)
- Status badge: "Error" with red background
- Error message: 13px, #9e9e9e, max 2 lines
- Action buttons: "Retry" (primary), "Troubleshoot" (secondary)
- Border: 1px solid rgba(219,68,55,0.3)
```

### 12.3 No Issues Found

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│        ╭─────────────╮                                                  │
│       ╱               ╲      100                                        │
│      │   ██████████   │      Your system is healthy! 🎉                 │
│      │   ██████████   │                                                 │
│       ╲   ████████   ╱       All 12 checks passed                       │
│        ╰─────────────╯                                                  │
│                                                                         │
│   Great job! No issues were found during the health check.              │
│   Consider running another scan in a week.                              │
│                                                                         │
│   [Schedule Reminder]                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

SPECIFICATIONS:
- Score: 100 with green gradient ring
- Celebratory message with optional emoji
- Suggestion for next action
- Optional: "Schedule Reminder" button
```

### 12.4 Module-Specific Empty States

```
DRIVERS MODULE (No outdated drivers):
├── Icon: ✓ large checkmark
├── Title: "All drivers are up to date"
├── Subtitle: "Last checked: {timestamp}"
└── Action: [Check Again]

EVENTS MODULE (No errors):
├── Icon: 📋 clipboard
├── Title: "No critical events found"
├── Subtitle: "Your event logs look clean"
└── Action: [View All Events]

STARTUP MODULE (No programs):
├── Icon: 🚀 rocket
├── Title: "No startup programs configured"
├── Subtitle: "Programs will appear here when added"
└── Action: [Learn More]
```

---

## 13. Implementation Notes

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

## 14. File Structure for Implementation

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

## 15. Modern UI Enhancements (Implemented)

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
ANIM_STAGGER_DELAY = 80     # Delay between staggered items
ANIM_FADE_DURATION = 300    # Fade-in animation duration
```

#### Staggered Fade-In Animation (Overview Page)

When the Overview page loads for the first time, widgets animate in sequentially:

```
STAGGERED FADE-IN SEQUENCE:
├── Tips Carousel       → Delay: 0ms,   Fade: 300ms
├── Health Summary Card → Delay: 80ms,  Fade: 300ms
├── Quick Status Grid   → Delay: 160ms, Fade: 300ms
├── Startup Card        → Delay: 240ms, Fade: 300ms
├── Boot Security Card  → Delay: 320ms, Fade: 300ms
├── System Info Card    → Delay: 400ms, Fade: 300ms
└── Activity Container  → Delay: 480ms, Fade: 300ms

IMPLEMENTATION:
├── Use QGraphicsOpacityEffect for fade
├── Start at opacity 0, animate to 1
├── Easing: OutCubic for smooth deceleration
├── Remove graphics effect after animation completes
│   (prevents rendering issues with child widgets like buttons)
└── Only animate on first show, not subsequent visits
```

#### Quick Status Card Hover Animation

Cards in the Quick Status grid have interactive hover effects:

```
HOVER EFFECT (GlassCard):
├── Lift: Card rises 3px (translateY animation)
├── Glow intensification: Up to 80% brighter glow
├── Border brightening: Border alpha increases on hover
├── Animation: 60fps smooth transition (16ms timer)
├── Easing: Smooth interpolation over ~200ms

IDLE → HOVER TRANSITION:
├── _hover_progress: 0.0 → 1.0
├── Card Y offset: 0px → -3px
├── Glow alpha multiplier: 1.0 → 1.8
├── Glow radius expansion: +4px on hover
└── Border width: 1.5px → 2.0px
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

#### HealthSummaryCard Gradient Background

The Health Summary card has a dynamic gradient background that subtly tints based on the health score:

```
GRADIENT BACKGROUND (Score-Based):
├── Direction: Diagonal (top-left to bottom-right)
├── Base color: Theme.BG_CARD
└── Tint blending: 8% tint color, 92% base color

SCORE THRESHOLDS:
├── Score >= 80: Green tint (Theme.GLOW_SUCCESS)
├── Score >= 50: Yellow tint (Theme.GLOW_WARNING)  
└── Score < 50:  Red tint (Theme.GLOW_ERROR)

IMPLEMENTATION:
gradient = QLinearGradient(0, 0, rect.width(), rect.height())
start_color = base_color
end_color = blend(base_color * 0.92, tint_color * 0.08)
gradient.setColorAt(0, start_color)
gradient.setColorAt(1, end_color)
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

## 16. Modern Table & List Design (Implemented)

This section documents the data table and list row components for displaying structured data with proper readability and user-friendliness.

### 16.0 Table UX Best Practices

```
CORE PRINCIPLES FOR USABILITY:

1. WHITESPACE & SPACING
   ├── Use generous padding (16px horizontal, 16px vertical minimum)
   ├── Group related data visually with spacing
   ├── Prevent cluttered appearance with breathing room
   └── Alternating row backgrounds aid scanning

2. ALIGNMENT RULES
   ├── Left-align all text content (titles, descriptions, names)
   ├── Right-align numeric values (for easy comparison)
   ├── Match header alignment to column data alignment
   └── Center only icons or very short status indicators

3. VISUAL HIERARCHY
   ├── Headers: Bold (600-700 weight), slightly larger or uppercase
   ├── Primary data: Medium weight (500), high contrast color
   ├── Secondary data: Regular weight (400), muted color (TEXT_SECONDARY)
   ├── Tertiary data: Smaller size, lowest contrast (TEXT_TERTIARY)
   └── Use font weight/color, NOT just size, to create hierarchy

4. MINIMIZE VISUAL NOISE
   ├── Avoid heavy borders between rows
   ├── Use subtle background alternation instead of grid lines
   ├── Let typography and spacing create structure
   └── Reserve borders for container edges only

5. FIXED HEADERS (for scrollable tables)
   ├── Keep column headers visible when scrolling
   ├── Use sticky positioning or separate header widget
   └── Maintain context for users scanning data

HANDLING LARGE/COMPLEX DATASETS:

1. OVERVIEW & DETAIL PATTERN
   ├── Show summary table with key columns only
   ├── Allow drill-down to detail view (modal or separate page)
   ├── Use "expand row" for inline details when appropriate
   └── Don't overwhelm with all data at once

2. PROGRESSIVE DISCLOSURE
   ├── Show 20-50 rows initially
   ├── "Load more" or "Show all" button for additional rows
   ├── Display count: "Showing 20 of 156 items"
   └── Consider virtual scrolling for 1000+ items

3. CONTEXTUAL INFORMATION
   ├── Use subtext under primary data (email under name, date under title)
   ├── Tooltips for truncated content or additional details
   ├── Status badges with descriptive text, not just colors
   └── Timestamps in relative format when recent ("2 hours ago")

INTERACTION PATTERNS:

1. HOVER EFFECTS
   ├── Subtle background highlight on row hover
   ├── Show action buttons on hover (or always if space permits)
   ├── Cursor change to pointer for clickable rows
   └── Don't rely solely on hover for mobile compatibility

2. ACTION BUTTONS
   ├── Place in dedicated column, typically rightmost
   ├── Primary action: Filled button with accent color
   ├── Secondary actions: Outline or ghost buttons
   ├── Destructive actions: Red text/outline, confirm before executing
   └── Group related actions, limit to 2-3 per row

3. SORTING & FILTERING
   ├── Essential for datasets > 10 items
   ├── Click header to sort (toggle asc/desc)
   ├── Visual indicator for active sort column
   └── Filter controls above table, not inline

WHEN TO USE ALTERNATIVES:

├── CARDS: When users focus on individual items, not comparing across rows
├── LISTS: For simpler, less structured data with fewer columns
├── ACCORDION: When each item has significant expandable content
└── TILES/GRID: For visual items (images, icons, thumbnails)
```

### 16.0.1 Table Design Philosophy

```
IMPLEMENTATION DECISIONS:
├── Use custom QFrame-based rows instead of QTableWidget
│   └── Reason: Better styling control, modern appearance, flexibility
├── Avoid native table widgets (QTableWidget, QTreeWidget)
│   └── Reason: Limited styling, platform-inconsistent appearance
├── Build tables from composable row components
│   └── Components: ModernListRow, ModernCategoryHeader, ModernListContainer
└── Support both simple lists and complex data grids

WHEN TO USE EACH COMPONENT:
├── ModernListRow: Single data item with title, subtitle, status, actions
├── ModernCategoryHeader: Group label for categorizing rows
├── ModernListContainer: Scrollable container for multiple rows
└── Custom grid layouts: For dashboard cards and multi-column data

TABLE DATA PATTERNS:
├── Sorted Data: Apply sorting in the data layer, rebuild rows
├── Filtered Data: Filter data first, then create rows for visible items
├── Paginated Data: Show subset of rows with "load more" or pagination
├── Grouped Data: Use category headers to separate logical groups
└── Searchable Data: Filter on input, recreate visible rows

PERFORMANCE GUIDELINES:
├── Limit visible rows to ~50-100 for smooth scrolling
├── Use "Show more" buttons for large datasets
├── Lazy load row content when possible
├── Clear and rebuild rows on data refresh (don't try to update in-place)
└── Use alternating row colors for datasets > 5 items
```

### 16.1 Design Principles

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

### 16.1.1 Column & Data Alignment

```
HORIZONTAL ALIGNMENT:
├── Text content: Left-aligned
├── Numeric values: Right-aligned
├── Status badges: Right-aligned (before chevron)
├── Action buttons: Right-aligned (after status)
├── Icons: Left-aligned (before title)
└── Chevrons: Right-most position

VERTICAL ALIGNMENT:
├── All row content: Vertically centered
├── Multi-line subtitles: Top-aligned within their space
└── Status icons: Vertically centered

DATA FORMATTING:
├── Dates: "YYYY-MM-DD" or "Dec 11, 2025" (human readable)
├── File sizes: "1.2 GB", "456 MB", "12 KB" (abbreviated)
├── Percentages: "85%" (no decimals unless < 1%)
├── Counts: "1,234" (comma-separated thousands)
├── Version numbers: "v1.2.3" or "1.2.3.456"
└── Truncation: Use ellipsis "..." for overflow, show full on tooltip

ROW CONTENT STRUCTURE:
┌──────────────────────────────────────────────────────────────────────────┐
│ [ICON] [TITLE + SUBTITLE]              [STATUS BADGE] [ACTIONS] [CHEVRON]│
│  18px   flex-1 (stretch)                 auto          auto       16px   │
└──────────────────────────────────────────────────────────────────────────┘
```

### 16.1.2 Action Button Styling

```
BUTTON TYPES IN TABLE ROWS:

PRIMARY BUTTON (use sparingly - 1 per table max):
├── Background: Theme.ACCENT (solid blue)
├── Text: White
├── Border: None
├── Use for: Main action user is expected to take
├── Example: "Run Scan", "Apply All"
└── Avoid: Having primary buttons on every row

SECONDARY BUTTON (default for row actions):
├── Background: Transparent
├── Text: Theme.ACCENT (blue)
├── Border: 1px solid Theme.ACCENT
├── Hover: Fill with Theme.ACCENT, text white
├── Use for: Individual row actions
└── Example: "Remove", "View", "Edit"

GHOST BUTTON (tertiary actions):
├── Background: Transparent
├── Text: Theme.TEXT_SECONDARY
├── Border: None
├── Hover: Background Theme.BG_CARD_HOVER
├── Use for: Low-priority or supplementary actions
└── Example: "Details", "Copy", "Share"

DESTRUCTIVE BUTTON (delete/remove with warning):
├── Background: Transparent
├── Text: Theme.ERROR (red)
├── Border: 1px solid Theme.ERROR
├── Hover: Fill with Theme.ERROR, text white
├── Use for: Permanent deletions requiring attention
└── Example: "Delete", "Uninstall"

BUTTON SIZING:
├── Height: 28px (compact for table rows)
├── Padding: 4px 14px
├── Font size: 11px
├── Font weight: 500-600
├── Border radius: 4px
└── Spacing between buttons: 8px
```

### 16.2 ModernListRow Component

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

### 16.3 ModernCategoryHeader Component

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

### 16.4 ModernListContainer Component

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

### 16.4.1 Table Empty & Loading States

```
EMPTY STATE (No Data):
├── Display centered message in container
├── Icon: Relevant empty icon (e.g., document, folder)
├── Title: "No items found" (14px, TEXT_PRIMARY)
├── Subtitle: Contextual message (12px, TEXT_SECONDARY)
├── Optional action button: "Refresh" or "Add Item"
└── Min height: 120px for empty container

LOADING STATE:
├── Display spinner centered in container
├── Use ModernSpinner component (24px)
├── Optional loading text: "Loading..." (12px, TEXT_SECONDARY)
├── Disable interactions during load
└── Min height: 80px for loading container

ERROR STATE:
├── Display error message with error icon
├── Icon: Error/warning icon in Theme.ERROR color
├── Title: Brief error description (14px, TEXT_PRIMARY)
├── Subtitle: Technical details if helpful (12px, TEXT_TERTIARY)
├── Action button: "Retry" or "View Details"
└── Border: 1px solid Theme.ERROR at 30% opacity

PARTIAL LOAD STATE:
├── Show available rows immediately
├── Display "Loading more..." at bottom
├── Use skeleton rows for pending items (optional)
└── "Show more" button for paginated data
```

### 16.5 Improved Stats Display

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

### 16.6 Usage Examples

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

### 16.7 Comparison: Before vs After

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
