---
name: Syntropic Console
colors:
  surface: '#111317'
  surface-dim: '#111317'
  surface-bright: '#37393d'
  surface-container-lowest: '#0c0e11'
  surface-container-low: '#1a1c1f'
  surface-container: '#1e2023'
  surface-container-high: '#282a2d'
  surface-container-highest: '#333538'
  on-surface: '#e2e2e6'
  on-surface-variant: '#c7c4d7'
  inverse-surface: '#e2e2e6'
  inverse-on-surface: '#2f3034'
  outline: '#908fa0'
  outline-variant: '#464554'
  surface-tint: '#c0c1ff'
  primary: '#c0c1ff'
  on-primary: '#1000a9'
  primary-container: '#8083ff'
  on-primary-container: '#0d0096'
  inverse-primary: '#494bd6'
  secondary: '#4edea3'
  on-secondary: '#003824'
  secondary-container: '#00a572'
  on-secondary-container: '#00311f'
  tertiary: '#7bd0ff'
  on-tertiary: '#00354a'
  tertiary-container: '#009bd1'
  on-tertiary-container: '#002d40'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#c4e7ff'
  tertiary-fixed-dim: '#7bd0ff'
  on-tertiary-fixed: '#001e2c'
  on-tertiary-fixed-variant: '#004c69'
  background: '#111317'
  on-background: '#e2e2e6'
  surface-variant: '#333538'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: -0.01em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.08em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1.5rem
  gutter-desktop: 1.5rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system delivers a high-density, low-friction operating canvas tailored for machine learning engineers, systems architects, and AI developers orchestrating autonomous multi-agent pipelines. Drawing directly from the restraint of high-tier conversational interfaces and the rigorous precision of developer tooling, the aesthetic combines technical brutalism's clarity with the nuanced, quiet luxury of minimalist dark UI.

### Design Aesthetic: High-Craft Technical Minimalist
- **Surfaces**: Tactile graphite and deep obsidian sheets framed by microscopic, low-contrast borders. Avoid generic pitch-black voids in favor of stepped dark zinc tones that retain spatial structure under low ambient light.
- **Micro-Interactions**: Crisp, instantaneous transitions (under 150ms cubic-bezier transitions) with zero rubber-banding or soft skeuomorphism. Interactive zones reveal themselves through hairline luminosity shifts and precise color-coded telemetry pings.
- **Information Architecture**: Uncluttered default view that exposes deep state on demand. Worktrees, agent orchestration graphs, and sub-process streams expand gracefully into context without disorienting layout shifts.

## Colors

The palette is engineered around dark ambient contrast, utilizing warm graphite undertones to eliminate ocular fatigue during extended engineering sessions. The hierarchy separates infrastructure state, generative model activity, and operational alerts through strictly assigned chromatic channels.

### Surface Tiers
- **Base Canvas (`#0D0F12`)**: Deep graphite foundation for the central chat viewport and structural grid guttering.
- **Surface Level 1 (`#16191E`)**: Primary sidebar panels, docked telemetry decks, and collapsible inspectors.
- **Surface Level 2 (`#1E232B`)**: Nested sub-containers, inline tool execution cards, agent worktree blocks, and input text areas.
- **Surface Elevated / Hover (`#252C37`)**: Interactive highlights, floating dropdowns, command palettes, and active context triggers.
- **Structural Borders (`#282F3A`)**: Hairline boundaries separating data surfaces; always kept sharp at 1px thickness.

### Accent Semantics
- **Indigo Orchestrator (`#6366F1`)**: Primary brand and agent autonomy indicator. Applied to active pipeline nodes, primary execution calls, and generative session states.
- **Emerald Health / Local Node (`#10B981`)**: Indicates successful compile steps, fully provisioned GPUs, active local inference endpoints, and 200 OK responses.
- **Electric Cyan (`#38BDF8`)**: Highlights real-time asynchronous streaming, retrieval-augmented generation (RAG) vector searches, and token synthesis metrics.
- **Amber Quota Warning (`#F59E0B`)**: Token rate limiting, compute budget consumption nearing threshold (>80%), and non-blocking dependency warnings.
- **Rose Error / Blocker (`#F43F5E`)**: Unhandled exceptions, process termination, context window overflow, and test harness failures.

## Typography

The typographic hierarchy enforces a dual-engine structure: `Inter` governs conversational outputs, systemic interface chrome, and editorial labels with tight optical balance, while `JetBrains Mono` handles all programmatic artifacts, token statistics, latency counts, model tags, and live code evaluations.

### Hierarchy & Usage
- **Conversational Stream (`body-lg`)**: Set at 16px with relaxed 26px line height for optimal scanning during multi-paragraph generation outputs.
- **Code & Syntax Execution (`code-md`)**: Distinct tabular numbers and strict alignment ensure side-by-side git diffs and terminal payloads align without horizontal jitter.
- **System Telemetry & Badges (`label-caps`)**: Uppercase monospace treatment applied to model identifiers (e.g., `CLAUDE-3.5-SONNET`, `O3-MINI`), GPU usage stats, and process badges.
- **Micro-labels (`code-sm`)**: Used inside real-time execution steps, latency timers (`42ms`), and dynamic cost trackers (`$0.0024/1k tokens`).

## Layout & Spacing

The workstation layout uses an asymmetrical, collapsible 3-zone structure anchored by a persistent navigation rail, a flexible central conversation/worktree canvas, and an on-demand contextual inspector.

### Grid & Dimensions
- **Navigation Rail / Sidebar**: Collapsed at `56px` (icon mode), expanding to a fixed `260px` drawer on hover or pin. Houses `Chat`, `Tasks`, `Knowledge / RAG`, `Harnesses & Models`, and `Settings`.
- **Center Canvas**: Maximum read width capped at `840px` for conversational threads to preserve character-per-line readability, dynamically expanding to `100%` when code diffs, DAG execution boards, or split terminals are activated.
- **Contextual Inspector**: Fixed width of `360px` docked to the right edge; collapses automatically beneath `1280px` viewport widths.
- **Bottom Status & Quota Bar**: Compact `36px` fixed horizontal band pinning system health, active rate limits, token expenditure, and active context model telemetry.

### Responsive Breakpoints
- **Mobile (< 768px)**: Sidebar shifts to overlay sheet triggered by a hamburger control. Inspector converts to tabbed overlay. Dynamic spacing throttles down: `margin: 1rem`, `gutter: 0.75rem`.
- **Tablet (768px - 1024px)**: Sidebar locks to icon-only mode (`56px`). Main view stays fluid.
- **Desktop (1025px+)**: Dual-pane or triple-pane fluid split. Margins scale to `2rem`.

## Elevation & Depth

Visual hierarchy does not use heavy drop-shadows or high-displacement blurs. Depth is achieved via strict planar luminance layering, structural 1px borders, and purposeful inner glows.

### Tonal Stratification
- **Plane 0 (Canvas Base)**: `#0D0F12` with no border.
- **Plane 1 (Structural Rail & Dock)**: `#16191E`, bounded by right/bottom borders of `1px solid #282F3A`.
- **Plane 2 (Cards, Interactive Surfaces, Inputs)**: `#1E232B`, bounded by `1px solid #282F3A`. Hovering increases border illumination to `#3B4454`.
- **Plane 3 (Modals, Overlays, Floating Command Palette)**: `#1E232B` supplemented with a sharp ambient halo: `0 16px 40px -8px rgba(0, 0, 0, 0.75)`, paired with a delicate top edge inner highlight (`inset 0 1px 0 0 rgba(255, 255, 255, 0.05)`).

### Atmospheric Cues
- **Terminal & Agent Glow**: When an autonomous agent is active, the container receives a subtle 1px border shift to `rgba(99, 102, 241, 0.35)` accompanied by a non-distracting `0 0 20px -5px rgba(99, 102, 241, 0.15)` localized glow.

## Shapes

The interface embraces a low-radius precision aesthetic (`roundedness: 1`). Soft 4px (`0.25rem`) corners define standard controls, while structural containers stay within an 8px (`0.5rem`) boundary. This preserves high spatial density, ensuring elements align crisp to the pixel grid without wasting valuable screen estate.

### Shape Geometry Rules
- **Micro-Controls (Chips, Badges, Tab Switchers)**: `rounded` (4px).
- **Cards, Terminal Blocks, Inline Step Containers**: `rounded-lg` (8px).
- **Modals, Floating Command Interfaces**: `rounded-xl` (12px).
- **Pill Exceptions**: Node status beacons, execution state pings, and notification counters retain full circular rounding (`50%` or `9999px`).

## Components

### Buttons
- **Primary**: Solid background `#6366F1`, text `#FFFFFF`, 4px radius, font `Inter` 13px weight 500. Height `32px`, horizontal padding `12px`. Hover shifts to `#4F46E5`. Active state scales subtly to `0.98`.
- **Secondary / Ghost**: Background transparent, border `1px solid #282F3A`, text `#E2E8F0`. Hover shifts background to `#1E232B` and border to `#3B4454`.
- **Destructive**: Background `rgba(244, 63, 94, 0.1)`, border `1px solid rgba(244, 63, 94, 0.3)`, text `#F43F5E`. Hover deepens background to `rgba(244, 63, 94, 0.2)`.

### Input Fields & Prompt Canvas
- **Conversational Input**: Multi-line growing textarea housed in a `#16191E` container with a `1px solid #282F3A` border and 8px border-radius. Focus applies a direct border highlight of `#6366F1` with an inner 1px glow. Text color `#F1F5F9`, placeholder `#64748B`. Integrated trailing actions (model picker, token count, file upload) dock directly within the bottom padding gutter.
- **Search & Filters**: Fixed height `32px`, font `JetBrains Mono` 12px, embedded leading search icon colored `#64748B`.

### Inline Task & Worktree Cards
- Collapsible cards representing agent execution stages (e.g., `git checkout -b feature/auth`, `RAG retrieval on 14 docs`, `Unit tests passing 4/4`).
- **Header**: `#1E232B` background, height `36px`, containing status indicator dot, task label (`Inter` 13px weight 500), execution duration (`JetBrains Mono` 11px `#94A3B8`), and a chevron toggle icon.
- **Body Content**: Expanded state reveals a `#0D0F12` code surface detailing stdout/stderr streams, vector distances, or LLM reasoning scratchpads.

### Badges & Telemetry Chips
- Compact dimensions: height `20px`, horizontal padding `6px`, font `JetBrains Mono` 10px uppercase.
- **Node Status**: Emerald tint (`rgba(16, 185, 129, 0.1)`) with `#10B981` text for active engines.
- **Agent Orchestrator**: Indigo tint (`rgba(99, 102, 241, 0.1)`) with `#818CF8` text.
- **Quota Limit Indicator**: Amber tint (`rgba(245, 158, 11, 0.1)`) with `#F59E0B` text.

### Dynamic Quota & Subscription Status Bar
- Fixed 36px bottom ribbon structured with `flex items-center justify-between`.
- Background `#16191E`, border-top `1px solid #282F3A`, padding horizontal `16px`.
- Left: Active model chip (`CLAUDE-3.5-SONNET`), context window progress bar (compact 4px height bar: filled percentage styled in `#38BDF8`).
- Right: Rate limits (`RPM: 42/50`, `TPM: 120k/200k`), latency metric (`p95: 380ms`), and operational node connection state.

### Lists & Navigation Links
- Sidebar navigation items operate at `36px` height with a 4px corner radius.
- Inactive state: `#94A3B8` icon and text.
- Active state: Background `#1E232B`, text `#FFFFFF`, border-left indicator `2px solid #6366F1`.
- Counter tags right-aligned in `JetBrains Mono` 11px muted gray.