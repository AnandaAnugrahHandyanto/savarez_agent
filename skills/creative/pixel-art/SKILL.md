---
name: pixel-art
description: Generate authentic pixel art PNG images using Pillow with distance-field shading and painterly layering. Edges emerge from color contrast, not traced outlines.
version: 2.0.0
category: creative
triggers:
  - pixel art
  - pixel drawing
  - sprite
  - 8-bit art
  - 16-bit art
  - game sprite
  - retro art
---

# Pixel Art Generation — Painterly Approach

Generate authentic pixel art as PNG images. Shapes are defined by **shading and color contrast**, not outlines. Edges emerge naturally where light meets dark — like painting on canvas, not coloring inside lines.

## Setup

```bash
/usr/bin/python3  # Pillow available here, NOT in hermes-agent venv
```

## Core Rules

1. **NO hard outline pixels** around shapes — let color contrast define edges
2. **NO grid character maps** — use coordinate math, not `"TTTOOMMLL"` strings
3. **NO outline-then-fill** — draw solid shapes with built-in shading
4. **YES distance-field shading** — smooth color gradients that create natural edges
5. **YES painterly layering** — bg → far → near → foreground, each layer overwrites naturally
6. **YES mathematical shapes** — ellipses, parametric curves, noise functions

## Palette Design

Define 5-7 colors per shape, running from deep shadow → base → highlight:

```python
# Example: brown fur (7 steps)
FUR = [
    (45, 28, 15),    # deep shadow
    (85, 55, 28),    # shadow
    (130, 85, 42),   # medium-dark
    (165, 112, 55),  # base
    (195, 148, 78),  # light
    (220, 185, 120), # highlight
    (238, 215, 165), # bright highlight
]
```

Colors should harmonize. Each major shape gets its own palette. For a 2-subject scene you'll have 2-3 palettes of 5-7 colors each.

## Key Technique: Distance-Field Shading

Instead of drawing an outline and filling it, define shapes mathematically and shade them from center to edge:

```python
def lerp_color(c1, c2, t):
    """Interpolate between two RGBA colors."""
    return tuple(int(c1[i] + (c2[i]-c1[i]) * t) for i in range(3)) + (255,)

def shade_shape(p, SZ, palette, dist_fn):
    """
    Shade a shape using distance from center/light.
    palette: list of (R,G,B) tuples from dark to light
    dist_fn: function(x, y) -> float, 0.0=highlight, 1.0=shadow/edge
    """
    for y in range(SZ):
        for x in range(SZ):
            t = dist_fn(x, y)
            if t <= 1.0:  # inside shape
                # Subtle noise for texture
                noise = ((x*7 + y*13) % 5) / 50.0
                t = min(1.0, max(0.0, t + noise))
                # Interpolate through palette
                idx = t * (len(palette) - 1)
                lo = int(idx)
                hi = min(lo+1, len(palette)-1)
                p[x, y] = lerp_color(palette[lo], palette[hi], idx - lo)
```

Light areas (low t) use early palette colors. Dark areas (high t) use later palette colors. Flip the mapping for convex vs concave — or just reverse the palette order.

### Common Distance Functions

**Ellipse:**
```python
def ellipse_dist(cx, cy, rx, ry):
    return lambda x, y: ((x-cx)/rx)**2 + ((y-cy)/ry)**2
```

**Brush stroke (along a curve):**
```python
def curve_dist(points, thickness):
    """points: list of (x,y), thickness: brush radius in pixels"""
    def dist(x, y):
        min_d = min(math.sqrt((x-px)**2 + (y-py)**2) for px,py in points)
        return min_d / thickness
    return dist
```

**Directional light shading (shadow on one side):**
```python
def lit_ellipse(cx, cy, rx, ry, light_x=-0.5, light_y=-0.7):
    """Ellipse with directional light. light_x/y: direction light comes FROM."""
    def dist(x, y):
        shape = ((x-cx)/rx)**2 + ((y-cy)/ry)**2
        if shape > 1.0: return 2.0  # outside
        # Light factor: dot product with light direction
        nx, ny = (x-cx)/rx, (y-cy)/ry  # normal approximation
        light = nx * light_x + ny * light_y
        return min(1.0, max(0.0, 0.5 + (1.0 - light) * 0.4))
    return dist
```

## Layer Order (Draw Back to Front)

```
1. Background sky/gradient
2. Far environment (trees, mountains, atmospheric glow)
3. Far subjects (large creatures, background characters)
4. Near subjects (foreground characters, the hero)
5. Ground/floor objects at character's feet
6. Particles and effects — ALWAYS last
```

Each layer simply draws on top. No z-index, no masking between layers. This is the painter's algorithm.

## Texture and Dithering

Add subtle texture with deterministic noise — probability 10-25% max:

```python
# Fur texture: occasionally swap base color with neighbor
for y in range(SZ):
    for x in range(SZ):
        if p[x,y][:3] == base_color and ((x*7+y*13) % 10) < 2:
            p[x,y] = lighter_color
```

**Warning:** Dithering above ~25% creates harsh checkerboard patterns. Keep it subtle.

## Small Details (Eyes, Nose, etc.)

Draw after main body. At 48-64px scale, 2-4 pixels is enough for eyes:

```python
# Eye: white 3x2 + dark pupil 2x1
for y in range(ey, ey+2):
    for x in range(ex, ex+3):
        p[x,y] = (240, 240, 245, 255)  # white
p[ex+1][ey+1] = (25, 18, 8, 255)  # pupil (offset = "looking" direction)
```

## Canvas Size Guide

| Detail Level | Canvas | Good For | Scale |
|---|---|---|---|
| Minimal | 16-24 | Icons, emojis | 16-20x |
| Standard | 32-48 | Single characters | 12-16x |
| Detailed | 48-80 | Scenes with 2+ subjects | 10-12x |
| Complex | 80-128 | Large detailed scenes | 8-10x |

## Save and Deliver

```python
SCALE = 12
big = img.resize((SZ*SCALE, SZ*SCALE), Image.NEAREST)
big.save(os.path.expanduser('~/my_art.png'))
```

Use `MEDIA:~/my_art.png` in your response for Telegram delivery.

## Complete Template

```python
#!/usr/bin/env /usr/bin/python3
from PIL import Image
import math, os

SZ = 48
img = Image.new('RGBA', (SZ, SZ), (0,0,0,0))
p = img.load()

# --- Palette ---
BG_TOP = (25, 60, 80)
BG_BOT = (40, 90, 110)
FUR = [(45,28,15), (85,55,28), (130,85,42), (165,112,55),
       (195,148,78), (220,185,120), (238,215,165)]
EYE_W = (240, 240, 245, 255)
EYE_P = (25, 18, 8, 255)

def lerp(c1, c2, t):
    return tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))+(255,)

def ellipse(cx, cy, rx, ry):
    return lambda x, y: ((x-cx)/rx)**2 + ((y-cy)/ry)**2

def shade(pal, dist_fn):
    for y in range(SZ):
        for x in range(SZ):
            t = dist_fn(x, y)
            if t <= 1.0:
                n = ((x*7+y*13)%5)/50.0
                t = min(1, max(0, t+n))
                idx = t*(len(pal)-1); lo=int(idx); hi=min(lo+1,len(pal)-1)
                p[x,y] = lerp(pal[lo], pal[hi], idx-lo)

# --- Draw layers ---
# 1. Background gradient
for y in range(SZ):
    t = y/SZ
    c = lerp(BG_TOP, BG_BOT, t)
    for x in range(SZ): p[x,y] = c

# 2. Subject body
shade(FUR, ellipse(24, 28, 14, 18))

# 3. Subject head  
shade(FUR, ellipse(24, 12, 9, 9))

# 4. Eye
for y in range(10,13):
    for x in range(20,24): p[x,y] = EYE_W
for y in range(11,13):
    for x in range(22,24): p[x,y] = EYE_P

# 5. Particles last
for gx,gy in [(5,10),(38,8),(10,35)]:
    p[gx,gy] = (255,220,80,255)

# --- Save ---
big = img.resize((SZ*12, SZ*12), Image.NEAREST)
out = os.path.expanduser('~/pixel_art.png')
big.save(out)
print(f"saved {out}")
```

## Pitfalls

- **Outline-then-fill** — never works at pixel scale. Gaps, overwrites, hours of debugging. Use distance-field shading instead.
- **Grid character maps** — one typo in `"TTTOOMMLL"` = broken image. Use coordinate math.
- **Too-small features** — 2-3 pixel curly tails read as rectangles. Make details 6-8+ pixels or use parametric curves.
- **Overwriting draw order** — body fill erases small features drawn before it. Draw appendages and features AFTER the body.
- **Dithering >25%** — creates harsh checkerboard. Keep 10-20%.
- **Wrong Python** — use `/usr/bin/python3` (has Pillow). Hermes venv doesn't have Pillow.
- **Fighting layers** — if a foreground element doesn't read as "in front," you drew it too early. Redraw it LAST.
- **Outline tracing replaces fills** — naive outlines overwrite interior pixels. If you must add outlines, use a boolean mask and only trace where shape meets background.

## Iterative Refinement

After generating, use `vision_analyze` to check readability. Ask specific questions:
- "Can you see the [tail/ears/eyes]?"
- "Does the [character] appear in front of the [creature]?"

If a feature isn't visible, it needs to be bigger or drawn later in the layer order. Typical iteration: 2-4 versions.