---
name: Acoustic Telemetry Engine
colors:
  surface: '#121416'
  surface-dim: '#121416'
  surface-bright: '#38393c'
  surface-container-lowest: '#0c0e10'
  surface-container-low: '#1a1c1e'
  surface-container: '#1e2022'
  surface-container-high: '#282a2c'
  surface-container-highest: '#333537'
  on-surface: '#e2e2e5'
  on-surface-variant: '#bcc9cd'
  inverse-surface: '#e2e2e5'
  inverse-on-surface: '#2f3033'
  outline: '#869397'
  outline-variant: '#3c494d'
  surface-tint: '#48d7f9'
  primary: '#a2e9ff'
  on-primary: '#003641'
  primary-container: '#42d3f5'
  on-primary-container: '#005869'
  inverse-primary: '#00687b'
  secondary: '#cef833'
  on-secondary: '#293500'
  secondary-container: '#b2db00'
  on-secondary-container: '#4a5d00'
  tertiary: '#ffd5d1'
  on-tertiary: '#68000a'
  tertiary-container: '#ffaea8'
  on-tertiary-container: '#a40217'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#afecff'
  primary-fixed-dim: '#48d7f9'
  on-primary-fixed: '#001f27'
  on-primary-fixed-variant: '#004e5d'
  secondary-fixed: '#c8f32c'
  secondary-fixed-dim: '#aed500'
  on-secondary-fixed: '#171e00'
  on-secondary-fixed-variant: '#3d4d00'
  tertiary-fixed: '#ffdad7'
  tertiary-fixed-dim: '#ffb3ad'
  on-tertiary-fixed: '#410004'
  on-tertiary-fixed-variant: '#930013'
  background: '#121416'
  on-background: '#e2e2e5'
  surface-variant: '#333537'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.03em
  headline-xl-mobile:
    fontFamily: Geist
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: JetBrains Mono
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.04em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.06em
  telemetry-num:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: -0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-sm: 0.75rem
  gutter-lg: 1.5rem
  margin: 1.5rem
  margin-sm: 1rem
  margin-lg: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system is constructed for mission-critical real-time voice infrastructure, streaming audio synthesis, and autonomous conversational agents. It deliberately rejects generic synthetic intelligence visual tropes—there are no iridescent purple gradients, amorphous glowing orbs, or consumer-grade decorative blurrings. 

The aesthetic is grounded in high-precision laboratory and flight-deck audio instruments:
- **Engineered Restraint:** Visual density communicates confidence and stability. Layouts privilege signal density over decorative airiness, maintaining instant scanability across high-throughput data streams.
- **Instrument Telemetry:** Surfaces behave like digital hardware consoles. State transitions, latency fluctuations, token throughput, and real-time audio pipeline events are manifested with surgical mechanical clarity.
- **Acoustic Focus:** Primary visual weight is reserved for acoustic states (carrier engagement, stream connection, packet drop rates, and decibel telemetry). All ambient UI remains deliberately muted in deep graphite and obsidian tones to avoid visual interference.

## Colors

The palette establishes an absolute obsidian foundation punctuated by surgical telemetry accents:

- **Foundation & Obsidian Tiers:**
  - `canvas-base`: `#0A0C0E` (Deep obsidian ink backdrop)
  - `surface-recessed`: `#111418` (Dark graphite for nested terminal consoles and sub-panels)
  - `surface-elevated`: `#161A20` (Tactile panels, inspector trays, metric cards)
  - `surface-overlay`: `#1E232B` (Interactive states, active tooltips, modal dialogs)

- **Structural Outlines & Boundaries:**
  - `border-subtle`: `#262D36` (Hairline component boundaries and structural grid dividers)
  - `border-contrast`: `#323B46` (Active focused borders and panel edges)

- **Signals & Telemetry:**
  - `signal-transport` (`#42D3F5`): Primary electric ice blue dedicated to network telemetry, active WebSocket transport, WebRTC peer status, buffer stats, and stream execution.
  - `signal-acoustic` (`#D4FF3A`): High-voltage acid lime used exclusively for active mic transmission, voice activity detection (VAD), live audio waveform peaks, and system execution commands.
  - `signal-warning` (`#F59E0B`): Jitter warning, audio packet slip, and network degradation warnings.
  - `signal-critical` (`#EF4444`): Hardware drop, connection termination, socket failure, and runtime exceptions.

- **Typographic Values:**
  - `text-primary`: `#F3F4F6` (Crisp stark warm white for headlines, vital readouts, and primary controls)
  - `text-secondary`: `#8B95A5` (Muted slate grey for field labels, secondary descriptions, and non-active data)
  - `text-data`: `#717E91` (Tabular metadata, packet indices, and millisecond timestamps)

## Typography

The typographic balance sets a high-density, technical tone:

- **Display & Headings (Geist):** Geist is deployed with neutral geometric precision. Tracking is tight across large scales, emphasizing stability, structure, and clarity in executive monitoring over marketing hyperbole.
- **Telemetric Core & Body (JetBrains Mono):** The interface treats data streams, session transcriptions, and agent diagnostics as code-adjacent primitives. Monospaced typography with tabular numeric alignment is standard across labels, continuous transcription streams, decibel figures, and millisecond counters.
- **Labels & Micro-Data:** Micro-labels utilize uppercase monospaced arrangements with extended tracking (`0.04em` to `0.06em`) to ensure legibility when reading dense configuration matrices or multi-channel audio tracks.

## Layout & Spacing

Layouts adhere to an orchestrated modular grid inspired by rack-mounted equipment and digital signal processing workspaces:

- **Grid Architecture:** Multi-pane operational console architecture. Desktop environments operate on a 12-column variable fluid grid system or a 3-column fixed docking layout (Left: Pipeline & Topology, Center: Real-Time Stream & Transcript, Right: Telemetry & Inspector).
- **Density Rhythm:** The design system maintains high vertical density. Component padding uses micro-increments (`space-xs` = 4px, `space-sm` = 8px, `space-md` = 12px) to prevent sprawling, inefficient viewports.
- **Reflow & Breakpoints:**
  - **Desktop (`>= 1280px`):** Full multi-pane instrumentation console. Grid gutters remain fixed at `1.5rem` (`gutter-lg`). All telemetry columns open concurrently.
  - **Tablet (`768px - 1279px`):** Center console remains primary; lateral telemetry panels convert to collapsible sliding drawers. Gutters shift to `1rem` (`gutter`).
  - **Mobile (`< 768px`):** Linearized single-column view. Audio trigger controls lock to a tactile persistent bottom controller. Gutters contract to `0.75rem` (`gutter-sm`) and canvas margins to `1rem` (`margin-sm`).

## Elevation & Depth

Visual hierarchy does not rely on soft drop shadows, atmospheric blurs, or floatation illusions. Depth is achieved via **structural tonal layering** and **razor border division**:

- **Layer Tiering:** 
  - Level 0 (Basebed): `#0A0C0E` defines the deepest canvas boundary.
  - Level 1 (Structural Insets): `#111418` hosts background monitoring matrices, waveform tracks, and diagnostic terminal outputs.
  - Level 2 (Module Panels): `#161A20` defines interactive cards and data surfaces.
  - Level 3 (Focus Overlays): `#1E232B` hosts contextual drop-downs, active tooltips, and floating audio mixer heads.
- **Borders over Shadows:** All containers define elevation purely through 1px crisp hairline borders (`#262D36`). Shadows are avoided, except for an ultra-subtle 4px non-diffused contact black (`rgba(0, 0, 0, 0.6)`) applied exclusively to interactive modal menus to separate overlapping planes.
- **Active State Illumination:** Selected or active components replace muted grey borders with a crisp 1px stroke of `#42D3F5` (Transport) or `#D4FF3A` (Audio Live), with zero surrounding diffuse glow.

## Shapes

The geometric signature is grounded, sharp, and utilitarian:

- **Corner Geometry:** Standard controls, metric inputs, cards, and modal dialogs maintain an ultra-tight radius of `0.25rem` (`roundedness: 1`). Sub-panels and inner status chips adopt `0.125rem` to preserve a clean architectural profile.
- **Strict Anti-Pill Standard:** Pill-shaped controls (`rounded-full`) are banned across standard UI inputs, metadata tags, and action buttons. Rounded-md and rounded-sm maintain an engineered look reminiscent of solid-state hardware.
- **Actuation Trigger Exception:** The solitary exception to strict rectangular geometry is the hardware-inspired primary Voice Actuation Module (the central mic/call controller), which utilizes circular tactile framing with hard outer bezel rings to designate its dedicated role as the primary human-to-machine physical interface.

## Components

### Buttons & Actuators
- **Primary Transport Action:** Background `#161A20`, hairline border `#42D3F5`, text `#42D3F5`, font `JetBrains Mono` 12px bold. Hover: Background `#42D3F5`, text `#0A0C0E`.
- **Live Voice Trigger (Active):** High-impact accent `#D4FF3A`, text `#0A0C0E`, font `JetBrains Mono` 13px bold, tracking tight. Active state displays an internal blinking hard-square audio tick.
- **Secondary / Utility:** Background `#111418`, hairline border `#262D36`, text `#8B95A5`. Hover: Border `#323B46`, text `#F3F4F6`.

### Telemetry Chips & Status Badges
- **Structure:** Tight container padding (2px vertical, 6px horizontal), radius `0.125rem`. 
- **States:**
  - *Active WebRTC:* Border `#42D3F5`, text `#42D3F5`, background `rgba(66, 211, 245, 0.08)`.
  - *Transmitting:* Border `#D4FF3A`, text `#D4FF3A`, background `rgba(212, 255, 58, 0.08)`.
  - *Degraded / Jitter:* Border `#F59E0B`, text `#F59E0B`, background `rgba(245, 158, 11, 0.08)`.

### Lists & Stream Tables
- **Execution:** Zero alternating zebra stripes. Separated by crisp 1px borders (`#262D36`). 
- **Row Architecture:** Monospaced timestamps (`#717E91`) aligned left, primary transcript/event tokens (`#F3F4F6`) center-left, and precision latency metrics (e.g., `42ms`, `99.8% TTFT`) right-aligned in tabular lining numerals. Hovering reveals a subtle graphite highlight (`#161A20`).

### Form Inputs & Signal Parameters
- **Fields:** Surface `#111418`, border `#262D36`, text `#F3F4F6`, placeholder `#717E91`. Focus state triggers an immediate 1px border `#42D3F5` without ambient outer halos or glowing rings.
- **Sliders & Step Adjusters (Gain, Temperature, Latency Cutoff):** 2px solid track `#262D36`, active fill `#42D3F5`, handle configured as a sharp 10px x 10px square marker (`#F3F4F6`) with zero corner rounding.

### Audio Waveform & Spectrum Modules
- **Oscilloscope / Spectrogram Containers:** Inset graphite beds (`#0A0C0E`) framed by `#262D36`.
- **Signal Traces:** Real-time audio rendering mapped in 1.5px hard lines or solid vertical histogram bars in `#D4FF3A` (Audio In) and `#42D3F5` (Agent Synthesis Response). Grid lines are mapped as 1px dashed reference markers at `-3dB`, `-6dB`, and `-12dB` in `#1E232B`.

### Cards & Telemetry Panels
- **Structure:** Background `#161A20`, border `#262D36`, radius `0.25rem`. Header areas feature an integrated hairline bottom border with monospaced uppercase metadata (`label-sm`), declaring session ID, codec (`Opus 48kHz`), and buffer sizing.