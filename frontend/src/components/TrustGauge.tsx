// Animated circular trust score gauge. SVG, no deps.
export function TrustGauge({ score, status }: { score: number; status: string }) {
  const size = 180
  const stroke = 14
  const radius = (size - stroke) / 2
  const circ = 2 * Math.PI * radius
  const offset = circ - (score / 100) * circ

  const color =
    status === "approved" ? "#10b981"
    : status === "conditional_approval" ? "#f59e0b"
    : "#f43f5e"

  return (
    <div className="relative inline-block" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          className="text-slate-200"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 1s ease-out" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-5xl font-bold tabular-nums" style={{ color }}>
          {score}
        </div>
        <div className="text-xs text-muted-foreground uppercase tracking-wider mt-1">
          Trust Score
        </div>
      </div>
    </div>
  )
}