# Quantum Computing Animation Examples

These scripts serve as advanced "Gold Standard" templates for generating Manim code and demonstrating how to orchestrate MathCode, Manim, and AI Voice generation into a single pipeline.

## 1. Jordan's Lemma (3D)
**File:** `jordans_lemma_3d.py`

This script demonstrates advanced `ThreeDScene` usage, camera orientation shifts, and drawing translucent 3D planes (mirrors) to map 3D objects onto 2D slices.

### The Pipeline Workflow
This video was created using a 3-step AI agent pipeline:

**Step 1: Formalization (MathCode)**
We used MathCode to formalize the underlying mathematics:
`echo "Formalize and prove Jordan's Lemma: The product of two reflections on a finite-dimensional Hilbert space is block-diagonalizable into 1D and 2D invariant subspaces." | ./run -p`

**Step 2: Video Generation (Manim)**
We generated the 3D visual using Manim:
`manim -qm jordans_lemma_3d.py Scene1_JordanLemma`

**Step 3: Audio & Muxing (Whisper/TTS & ffmpeg)**
We generated an ELI5 voiceover using Hermes Agent's TTS tool and stitched it together:
`ffmpeg -y -i media/videos/jordans_lemma_3d/720p30/Scene1_JordanLemma.mp4 -i voiceover.mp3 -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 -shortest final_jordan_with_audio.mp4`

## 2. Bacon-Shor Lattice (2D)
**File:** `bacon_shor_lattice.py`

Demonstrates 2D grid generation, grouping specific rows/columns, and highlighting overlaps. This represents the intersection parity of the X and Z stabilizers.

### Testing the Examples
To test that these examples render correctly on your machine, run the following from within this directory:
```bash
# Render the 3D Jordan's Lemma animation (draft quality)
manim -ql jordans_lemma_3d.py Scene1_JordanLemma

# Render the 2D Bacon-Shor Lattice animation (draft quality)
manim -ql bacon_shor_lattice.py Scene2_Intersection
```

