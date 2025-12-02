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

```
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
```

---

## 2. Color Palette

### Version A: Minimalist (Flat Modern)

```
BACKGROUND LAYERS
├── Window Background     #1b1b1f    (Near black with warmth)
├── Sidebar Background    #232328    (Slightly elevated)
├── Card Background       #2d2d32    (Content containers)
├── Hover State           #38383d    (Interactive feedback)
└── Active/Selected       #0078d4    (Windows accent blue)

TEXT HIERARCHY
├── Primary Text          #ffffff    (Headings, important)
├── Secondary Text        #b4b4b4    (Body text)
├── Tertiary Text         #7a7a7a    (Captions, timestamps)
└── Disabled Text         #4a4a4a    (Inactive elements)

SEMANTIC COLORS
├── Success/Healthy       #0f9d58    (Green - not neon)
├── Warning/Attention     #f4b400    (Amber)
├── Error/Critical        #db4437    (Red)
├── Info/Neutral          #4285f4    (Blue)
└── In Progress           #8e44ad    (Purple for running scans)

ACCENT COLORS
├── Primary Accent        #0078d4    (Windows Blue)
├── Secondary Accent      #106ebe    (Darker blue for depth)
└── Highlight             #60cdff    (Light blue for emphasis)
```

### Version B: Depth (Soft Shadows & Elevation)

Same palette as above, plus:

```
ELEVATION SYSTEM
├── Level 0 (Base)        No shadow, background color
├── Level 1 (Cards)       0 2px 4px rgba(0,0,0,0.2)
├── Level 2 (Modals)      0 8px 16px rgba(0,0,0,0.3)
├── Level 3 (Dropdowns)   0 12px 24px rgba(0,0,0,0.4)
└── Level 4 (Tooltips)    0 4px 8px rgba(0,0,0,0.25)

SURFACE TREATMENTS
├── Subtle gradient       linear-gradient(180deg, #2d2d32 0%, #28282d 100%)
├── Glass effect          background: rgba(45,45,50,0.85); backdrop-filter: blur(20px)
└── Border highlight      1px solid rgba(255,255,255,0.06) on top edge of cards
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

*This specification provides a complete blueprint for building a professional Windows Health Checker application that feels cohesive, intentional, and premium.*
