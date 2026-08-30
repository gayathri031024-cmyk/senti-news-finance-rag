interface StatusBadgeProps {
  state: "checking" | "connected" | "degraded" | "unreachable";
}

const STYLES: Record<StatusBadgeProps["state"], string> = {
  checking: "bg-slate-100 text-slate-600 border-slate-200",
  connected: "bg-emerald-50 text-emerald-700 border-emerald-200",
  degraded: "bg-amber-50 text-amber-700 border-amber-200",
  unreachable: "bg-rose-50 text-rose-700 border-rose-200",
};

const LABELS: Record<StatusBadgeProps["state"], string> = {
  checking: "Checking backend…",
  connected: "Backend connected",
  degraded: "Backend degraded",
  unreachable: "Backend unreachable",
};

const DOT_STYLES: Record<StatusBadgeProps["state"], string> = {
  checking: "bg-slate-400 animate-pulse",
  connected: "bg-emerald-500",
  degraded: "bg-amber-500",
  unreachable: "bg-rose-500",
};

export function StatusBadge({ state }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium ${STYLES[state]}`}
    >
      <span className={`h-2 w-2 rounded-full ${DOT_STYLES[state]}`} />
      {LABELS[state]}
    </span>
  );
}
