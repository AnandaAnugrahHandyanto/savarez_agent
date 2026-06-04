/**
 * Minimal dashboard backdrop.
 *
 * Keep the visual foundation intentionally plain: a single solid canvas from
 * the active theme. This avoids image backgrounds, glow layers, and grain so
 * dashboard content stays readable with the simple Arial/dark-text theme.
 */
export function Backdrop() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-[1]"
      style={{ backgroundColor: "var(--background-base)" }}
    />
  );
}
