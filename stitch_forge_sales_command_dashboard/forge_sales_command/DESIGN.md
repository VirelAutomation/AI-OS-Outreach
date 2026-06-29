---
name: Forge Sales Command
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#3a3939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#e9bcb6'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#af8782'
  outline-variant: '#5e3f3a'
  surface-tint: '#ffb4aa'
  primary: '#ffb4aa'
  on-primary: '#690003'
  primary-container: '#e3000f'
  on-primary-container: '#fff4f2'
  inverse-primary: '#c0000b'
  secondary: '#c6c6c7'
  on-secondary: '#2f3131'
  secondary-container: '#454747'
  on-secondary-container: '#b4b5b5'
  tertiary: '#c8c6c5'
  on-tertiary: '#303030'
  tertiary-container: '#717070'
  on-tertiary-container: '#f8f5f4'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdad5'
  primary-fixed-dim: '#ffb4aa'
  on-primary-fixed: '#410001'
  on-primary-fixed-variant: '#930006'
  secondary-fixed: '#e2e2e2'
  secondary-fixed-dim: '#c6c6c7'
  on-secondary-fixed: '#1a1c1c'
  on-secondary-fixed-variant: '#454747'
  tertiary-fixed: '#e4e2e1'
  tertiary-fixed-dim: '#c8c6c5'
  on-tertiary-fixed: '#1b1c1c'
  on-tertiary-fixed-variant: '#474746'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-sm:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.0'
    letterSpacing: 0.1em
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.0'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  gutter: 20px
  margin: 32px
---

## Brand & Style

The design system is engineered for high-stakes environments where speed and precision are paramount. The brand personality is **Commanding, Fast-paced, and Data-driven**, reflecting an AI agency that operates at the cutting edge of sales automation. 

The visual style is a hybrid of **Minimalist-Dark** and **Glassmorphism**, characterized by a deep monochromatic foundation interrupted by surgical strikes of high-intensity red. The aesthetic evokes a "war room" atmosphere—professional yet aggressive. Expect heavy use of translucency, sharp geometric precision, and subtle inner glows that simulate illuminated hardware interfaces. Whitespace is used strategically to create focus, not just breathing room.

## Colors

This design system utilizes a high-contrast, dark-dominant palette to minimize eye strain during long sessions while highlighting critical KPIs.

- **Base (Neutral):** `#0a0a0a`. The absolute foundation. All surfaces derive from this value with varying levels of transparency.
- **Action (Primary):** `#e3000f`. A sharp, aggressive red reserved for primary actions, critical alerts, and momentum indicators.
- **Data (Secondary):** `#ffffff`. High-purity white used for primary text and high-contrast iconography.
- **Structural (Tertiary):** `#2a2a2a`. Used for borders and "inactive" glass states to maintain structural integrity without visual noise.

**Glass Effects:** Surfaces should use `rgba(255, 255, 255, 0.03)` for backgrounds with a `20px` backdrop-blur and a `1px` stroke of `rgba(255, 255, 255, 0.1)`.

## Typography

The typography system prioritizes technical clarity and a modern, engineered feel. 

**Geist** is the primary typeface, chosen for its Swiss-inspired precision and developer-centric aesthetic. It handles all UI text and large headlines. **JetBrains Mono** is utilized for metadata, labels, and raw data values (like currency or conversion rates) to emphasize the analytical, AI-driven nature of the dashboard.

All headlines should favor tighter letter-spacing to appear more "locked-in" and aggressive. Labels should always be uppercase with increased tracking to differentiate them from body content.

## Layout & Spacing

The design system employs a **12-column Fluid Grid** for dashboard views and a **Fixed Grid** for specialized settings or modal views.

- **The 4px Rule:** All spacing increments must be multiples of 4px to ensure perfect alignment of dense data tables.
- **Command Layout:** Sidebars are fixed at `280px` to maintain a consistent control center. Content areas use a fluid width with a maximum container of `1600px` to prevent data dispersion on ultra-wide monitors.
- **Mobile Reflow:** On mobile, the 12-column grid collapses to a single column. Spacing `xl` (40px) is reduced to `lg` (24px) to maximize screen real estate.

## Elevation & Depth

Hierarchy is established through **Backdrop Blur** and **Inner Glows** rather than traditional drop shadows.

- **Level 0 (Base):** Deep Black `#0a0a0a`. No transparency.
- **Level 1 (Cards):** Subsurface glass. Background: `rgba(255, 255, 255, 0.03)`. Blur: `20px`. Border: `1px solid rgba(255, 255, 255, 0.08)`.
- **Level 2 (Modals/Popovers):** Elevated glass. Background: `rgba(20, 20, 20, 0.8)`. Blur: `40px`. Border: `1px solid rgba(255, 255, 255, 0.15)`.
- **Focus State:** Elements in focus or active states receive a subtle `0px 0px 15px rgba(227, 0, 15, 0.2)` red outer glow to signal activity.

## Shapes

The shape language is **Soft (0.25rem)**. This slight rounding provides a professional, modern feel while maintaining the aggressive, sharp-edged intent of the brand.

- **Standard Elements:** 4px radius (Buttons, Inputs, Small Cards).
- **Large containers:** 8px radius (Main Dashboard Panes, Kanban Columns).
- **Interactive Indicators:** Elements like status pips or small toggle handles remain perfectly square or use a 2px radius to emphasize a mechanical feel.

## Components

### Buttons
- **Primary:** Solid `#e3000f` background with white text. No border. On hover, increase brightness.
- **Ghost:** Transparent background with a `1px` white stroke at `0.2` opacity. White text.

### Progress Rings & Funnels
- Progress rings use a thick `4px` stroke. The "track" is `rgba(255,255,255,0.05)`, and the "fill" is a gradient from `#e3000f` to `#800008`.
- Funnel charts should use stepped glass layers, with the widest part of the funnel being the most transparent.

### Data Tables
- Header rows use `label-caps` typography with a `1px` bottom border of `rgba(255,255,255,0.1)`.
- Row hover states should utilize a subtle `rgba(255, 255, 255, 0.02)` background highlight.

### Kanban Boards
- Columns are transparent glass containers. Cards inside use Level 1 elevation.
- Task priority is indicated by a vertical `2px` accent line on the left side of the card (Red for high, Grey for low).

### Inputs
- Background: `rgba(0, 0, 0, 0.3)`. Border: `1px solid rgba(255, 255, 255, 0.1)`.
- Active state: Border changes to `#e3000f` with a subtle inner red glow.