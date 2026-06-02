import { FileWarning, LockKeyhole, Shield } from "lucide-react";

const envelopeStatus = [
  "Display only",
  "No active authorization",
  "Operational actions locked",
  "Discussion/status only",
];

const envelopeFields = [
  "Active lane: Unset",
  "Active mode: Unset",
  "Execution boundary: No active authorization",
  "Allowed actions: None declared",
  "Forbidden actions: Unknown",
  "Checkpoint: None",
  "Repo state: Unknown / not probed",
  "Evidence: No envelope evidence attached",
  "Data source: No persisted envelope",
];

export function ActiveEnvelopePanel() {
  return (
    <section className="font-readable-ui rounded-2xl border border-amber-400/25 bg-[linear-gradient(135deg,rgba(34,23,8,0.78),rgba(7,15,15,0.94))] p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.04)] lg:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-amber-400/30 bg-amber-500/10 px-3 py-1 text-xs uppercase tracking-wide text-amber-100">
            <LockKeyhole className="h-3.5 w-3.5" />
            No persisted envelope
          </div>
          <h2 className="text-xl font-semibold text-text-primary">No Active Task Envelope</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-text-secondary">
            No persisted envelope is attached, so there is no active authorization for this Mission Control surface.
          </p>
        </div>

        <div className="grid gap-2 text-sm sm:grid-cols-2 lg:min-w-96">
          {envelopeStatus.map((item) => (
            <div key={item} className="rounded-xl border border-[#3d3a24] bg-black/25 px-3 py-2 text-amber-100">
              {item}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="rounded-xl border border-[#284848] bg-black/25 p-3">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-midground">
            <Shield className="h-4 w-4" />
            Authorization boundary
          </div>
          <div className="grid gap-2 text-sm">
            {envelopeFields.slice(0, 6).map((line) => (
              <div key={line} className="rounded-lg border border-white/10 bg-black/25 px-3 py-2 text-text-secondary">
                {line}
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[#284848] bg-black/25 p-3">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-midground">
            <FileWarning className="h-4 w-4" />
            Evidence posture
          </div>
          <div className="grid gap-2 text-sm">
            {envelopeFields.slice(6).map((line) => (
              <div key={line} className="rounded-lg border border-white/10 bg-black/25 px-3 py-2 text-text-secondary">
                {line}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
