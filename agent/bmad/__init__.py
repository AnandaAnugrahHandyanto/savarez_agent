"""Project-aware BMAD-METHOD adapter for Hermes.

The adapter is optional and read-mostly. It exposes project-local BMAD skills
only when a `_bmad/` installation is detected from the active project path or
when callers explicitly ask from such a path.
"""
