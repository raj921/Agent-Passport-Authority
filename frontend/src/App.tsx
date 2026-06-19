import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { TrustGauge } from "@/components/TrustGauge"
import { submitPassport, getPassport, listPassports, type Passport } from "@/lib/api"
import {
  Shield, Send, Sparkles, Users, CheckCircle2, XCircle, AlertCircle, Clock,
  ChevronRight, Loader2, ShieldCheck, ScrollText, Target,
} from "lucide-react"

function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "approved": return "default"
    case "conditional_approval": return "secondary"
    case "rejected": return "destructive"
    default: return "outline"
  }
}

function statusLabel(status: string) {
  switch (status) {
    case "approved": return "Approved"
    case "conditional_approval": return "Conditional"
    case "rejected": return "Rejected"
    default: return "Pending"
  }
}

const INJECTION_PATTERNS = [
  /ignore\s+(previous\s+)?instructions?/i,
  /you\s+(are\s+)?must\s+(not\s+)?(ignore|disregard|reveal)/i,
  /system\s*:?\s*override/i,
  /new\s+instructions?\s*:?/i,
  /prompt\s+injection/i,
  /jailbreak/i,
  /DAN\b/i,
]

const MALICIOUS_PACKAGE_PATTERNS = [
  /[\w-]*(?:malware|trojan|backdoor|exploit|rootkit|keylogger|ransomware|spyware|dropper|stealer|miner)[\w-]*/i,
  /npm\s+install\s+.{0,40}(?:malware|exploit|hijack|suspicious)/i,
  /pip\s+install\s+.{0,40}(?:malware|exploit|hijack|suspicious)/i,
  /curl\s+.{0,60}\|.{0,20}(?:bash|sh|zsh)/i,
  /wget\s+.{0,60}(?:\.exe|\.sh|\.bat)/i,
  /eval\s*\(\s*(?:base64|atob|req\.body)/i,
  /child_process|spawn|execSync|shelljs/i,
]

function detectThreats(text: string): string | null {
  if (INJECTION_PATTERNS.some(p => p.test(text))) {
    return "Possible prompt injection or instruction override detected."
  }
  if (MALICIOUS_PACKAGE_PATTERNS.some(p => p.test(text))) {
    return "Potential malicious package or command detected."
  }
  return null
}

const SPECIALISTS = [
  { name: "Security Probe", role: "Threat & risk analysis", icon: ShieldCheck, color: "from-rose-500 to-orange-500" },
  { name: "Compliance Agent", role: "Policy & regulatory", icon: ScrollText, color: "from-amber-500 to-yellow-500" },
  { name: "Capability Verifier", role: "Least-privilege check", icon: Target, color: "from-emerald-500 to-teal-500" },
]

export default function App() {
  const [agentName, setAgentName] = useState("")
  const [context, setContext] = useState("")
  const [perms, setPerms] = useState("")
  const [current, setCurrent] = useState<Passport | null>(null)
  const [history, setHistory] = useState<Passport[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function refreshHistory() {
    try { setHistory(await listPassports()) } catch {}
  }

  useEffect(() => { refreshHistory() }, [])

  useEffect(() => {
    if (!current || current.status !== "pending") return
    const t = setInterval(async () => {
      try {
        const p = await getPassport(current.request_id)
        setCurrent(p)
        if (p.status !== "pending") refreshHistory()
      } catch {}
    }, 2000)
    return () => clearInterval(t)
  }, [current?.request_id, current?.status])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    const threat = detectThreats(agentName + " " + context + " " + perms)
    if (threat) {
      setError(threat + " Request blocked.")
      return
    }
    setSubmitting(true)
    try {
      const permsList = perms.split(",").map(p => p.trim()).filter(Boolean)
      const p = await submitPassport(agentName, context, permsList)
      setCurrent(p)
      refreshHistory()
    } catch (e: any) {
      setError(e.message ?? "submit failed")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-[linear-gradient(to_bottom,#fff,#ffffff_50%,#f3f0ff_100%)] relative overflow-hidden">
      {/* Decorative grid + radial — from 21st.dev hero pattern */}
      <div
        className="absolute inset-x-0 top-0 -z-10 h-[700px] opacity-60
        bg-[linear-gradient(to_right,#f0e8ff_1px,transparent_1px),linear-gradient(to_bottom,#f0e8ff_1px,transparent_1px)]
        bg-[size:6rem_5rem]
        [mask-image:radial-gradient(ellipse_80%_50%_at_50%_0%,#000_50%,transparent_100%)]"
      />
      <div className="absolute left-1/2 top-[280px] -z-10 h-[500px] w-[1100px] -translate-x-1/2 rounded-[100%] border-[#B48CDE]/40 bg-[radial-gradient(closest-side,#fff_50%,transparent_90%)] animate-pulse" />

      {/* === HEADER === */}
      <header className="border-b bg-white/70 backdrop-blur-xl sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl bg-gradient-to-br from-violet-500 via-indigo-500 to-blue-600 grid place-items-center text-white shadow-lg shadow-violet-500/30">
              <Shield className="size-5" />
            </div>
            <div>
              <div className="font-semibold leading-tight text-base">Agent Passport Authority</div>
              <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                <span className="inline-block size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Multi-agent review · Band platform
              </div>
            </div>
          </div>
          <Badge variant="outline" className="font-mono text-xs gap-1.5">
            <Users className="size-3" />
            4 agents · live
          </Badge>
        </div>
      </header>

      {/* === HERO === */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-12 text-center relative">
        <motion.a
          href="#"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="group inline-block"
        >
          <span className="text-xs text-gray-600 mx-auto px-4 py-1.5 bg-gradient-to-tr from-violet-300/10 via-violet-200/10 to-transparent border border-violet-300/30 rounded-full tracking-tight uppercase flex items-center justify-center">
            <Sparkles className="size-3 mr-1.5" />
            Live demo
            <ChevronRight className="inline w-3.5 h-3.5 ml-1 transition-transform duration-300 group-hover:translate-x-1" />
          </span>
        </motion.a>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mt-6 text-balance bg-gradient-to-br from-slate-950 from-30% to-slate-700/40 bg-clip-text py-4 text-5xl font-semibold leading-none tracking-tighter text-transparent sm:text-6xl md:text-7xl"
        >
          Passport screening,<br />for agents
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mt-6 mx-auto max-w-2xl text-lg tracking-tight text-gray-600 md:text-xl"
        >
          Submit what the agent does and what content it handles. Three specialists screen it like a passport office: safe use gets cleared, malicious use gets rejected.
        </motion.p>
      </section>

      <main className="max-w-6xl mx-auto px-6 pb-16 relative">
        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          {/* === SUBMIT FORM === */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            <Card className="border-violet-100 shadow-xl shadow-violet-500/5 overflow-hidden relative">
              <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-violet-400 to-transparent" />
              <CardContent className="p-6">
                <div className="flex items-center gap-3 mb-5">
                  <div className="size-9 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 grid place-items-center shadow-md shadow-violet-500/30">
                    <Send className="size-4 text-white" />
                  </div>
                  <div>
                    <div className="font-semibold">Screen agent</div>
                    <div className="text-xs text-muted-foreground">Check intent, content, and tools</div>
                  </div>
                </div>

                <form onSubmit={onSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="agent">Agent name</Label>
                    <Input
                      id="agent"
                      value={agentName}
                      onChange={e => setAgentName(e.target.value)}
                      placeholder="e.g. InvoiceBot"
                      required
                      className="text-base"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="perms">Requested permissions</Label>
                    <Input
                      id="perms"
                      value={perms}
                      onChange={e => setPerms(e.target.value)}
                      placeholder="invoice_read, invoice_write"
                      required
                      className="font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground">Comma-separated</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="context">What information or package?</Label>
                    <textarea
                      id="context"
                      value={context}
                      onChange={e => setContext(e.target.value)}
                      placeholder="Examples: Processes refund CSV exports; uses npm:papaparse@5. Never sends payments or exports private data."
                      required
                      className="min-h-28 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
                    />
                    <p className="text-xs text-muted-foreground">Describe data, content, or packages the agent uses. Prompt-injection, malicious commands, or suspicious packages will be rejected.</p>
                  </div>
                  <Button
                    type="submit"
                    disabled={submitting}
                    className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 shadow-lg shadow-violet-500/30"
                    size="lg"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="size-4 mr-2 animate-spin" />
                        Submitting…
                      </>
                    ) : (
                      <>
                        Start screening
                        <ChevronRight className="size-4 ml-1" />
                      </>
                    )}
                  </Button>
                  {error && <p className="text-sm text-rose-600">{error}</p>}
                </form>
              </CardContent>
            </Card>
          </motion.div>

          {/* === RESULT CARD === */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            <Card className="border-slate-200 shadow-xl shadow-slate-500/5 overflow-hidden">
              <div className="bg-gradient-to-br from-slate-50 via-white to-violet-50/40 px-6 pt-5 pb-4 border-b">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="size-9 rounded-lg bg-gradient-to-br from-slate-700 to-slate-900 grid place-items-center shadow-md">
                      <Shield className="size-4 text-white" />
                    </div>
                    <div>
                      <div className="font-semibold">Latest decision</div>
                      <div className="text-xs text-muted-foreground font-mono">
                        {current ? `${current.request_id.slice(0, 8)}…` : "Awaiting submission"}
                      </div>
                    </div>
                  </div>
                  <AnimatePresence mode="wait">
                    {current && (
                      <motion.div
                        key={current.status}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                      >
                        <Badge variant={statusVariant(current.status)} className="text-xs">
                          {statusLabel(current.status)}
                        </Badge>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>

              <CardContent className="pt-6">
                {!current && (
                  <div className="text-sm text-muted-foreground py-12 text-center">
                    Submit an agent above to see the committee's decision.
                  </div>
                )}

                {current && current.status === "pending" && (
                  <div className="space-y-6 py-4">
                    <div className="text-center">
                      <div className="text-sm text-muted-foreground mb-1">Reviewing</div>
                      <div className="text-2xl font-semibold bg-gradient-to-br from-slate-900 to-violet-900 bg-clip-text text-transparent">
                        {current.agent_name}
                      </div>
                    </div>
                    <div className="space-y-2">
                      {SPECIALISTS.map((s, i) => {
                        const Icon = s.icon
                        return (
                          <motion.div
                            key={s.name}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.4, delay: i * 0.15 }}
                            className="flex items-center gap-3 p-3 rounded-lg bg-gradient-to-r from-slate-50 to-white border border-slate-100 hover:shadow-md transition-shadow"
                          >
                            <div className={`size-9 rounded-lg bg-gradient-to-br ${s.color} grid place-items-center text-white shadow-sm shrink-0`}>
                              <Icon className="size-4" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="font-medium text-sm">{s.name}</div>
                              <div className="text-xs text-muted-foreground">{s.role}</div>
                            </div>
                            <Loader2 className="size-4 text-violet-500 animate-spin" />
                          </motion.div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {current && current.result && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5 }}
                    className="space-y-5"
                  >
                    <div className="flex flex-col items-center gap-2">
                      <TrustGauge score={current.result.trust_score} status={current.result.status} />
                      <div className="text-xs text-muted-foreground">
                        for <span className="font-medium text-slate-700">{current.agent_name}</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div className="rounded-lg bg-gradient-to-br from-emerald-50 to-emerald-100/50 border border-emerald-200 p-3">
                        <div className="flex items-center gap-1.5 text-xs text-emerald-700 uppercase tracking-wide font-medium mb-1.5">
                          <CheckCircle2 className="size-3" />
                          Approved
                        </div>
                        <div className="font-mono text-emerald-900 text-xs">
                          {current.result.approved_permissions.length === 0
                            ? <span className="text-muted-foreground italic">none</span>
                            : current.result.approved_permissions.map((p, i) => <div key={i}>{p}</div>)}
                        </div>
                      </div>
                      <div className="rounded-lg bg-gradient-to-br from-rose-50 to-rose-100/50 border border-rose-200 p-3">
                        <div className="flex items-center gap-1.5 text-xs text-rose-700 uppercase tracking-wide font-medium mb-1.5">
                          <XCircle className="size-3" />
                          Blocked
                        </div>
                        <div className="font-mono text-rose-900 text-xs">
                          {current.result.blocked_permissions.length === 0
                            ? <span className="text-muted-foreground italic">none</span>
                            : current.result.blocked_permissions.map((p, i) => <div key={i}>{p}</div>)}
                        </div>
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground uppercase tracking-wide font-medium mb-1.5">
                        <AlertCircle className="size-3" />
                        Rationale
                      </div>
                      <p className="text-sm leading-relaxed text-slate-700">{current.result.rationale}</p>
                    </div>
                  </motion.div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* === TIMELINE (21st.dev style) === */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <Card className="border-slate-200 shadow-lg overflow-hidden">
            <div className="px-6 pt-6 pb-4 border-b bg-gradient-to-br from-white to-slate-50/50">
              <div className="flex items-center gap-3">
                <div className="size-9 rounded-lg bg-gradient-to-br from-slate-700 to-slate-900 grid place-items-center shadow-md">
                  <Clock className="size-4 text-white" />
                </div>
                <div>
                  <div className="font-semibold">Activity</div>
                  <div className="text-xs text-muted-foreground">Recent passport decisions</div>
                </div>
              </div>
            </div>

            <CardContent className="pt-6">
              {history.length === 0 && (
                <div className="text-sm text-muted-foreground py-8 text-center">No activity yet.</div>
              )}
              <ul className="space-y-1">
                <AnimatePresence initial={false}>
                  {history.map((p, i) => (
                    <motion.li
                      key={p.request_id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.2, delay: Math.min(i * 0.02, 0.3) }}
                      onClick={() => setCurrent(p)}
                      className="px-3 py-3 flex items-center gap-4 cursor-pointer hover:bg-gradient-to-r hover:from-violet-50/50 hover:to-transparent rounded-lg transition-all"
                    >
                      <div className="relative">
                        <div className={`size-2.5 rounded-full shrink-0 ${
                          p.status === "pending" ? "bg-violet-500"
                          : p.status === "approved" ? "bg-emerald-500"
                          : p.status === "rejected" ? "bg-rose-500"
                          : "bg-amber-500"
                        }`} />
                        {p.status === "pending" && (
                          <div className="absolute inset-0 rounded-full bg-violet-500 animate-ping opacity-75" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{p.agent_name}</div>
                        <div className="text-xs text-muted-foreground truncate font-mono">
                          {p.requested_permissions.join(", ")}
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {p.result && (
                          <span className={`text-sm font-bold tabular-nums ${
                            p.result.trust_score >= 70 ? "text-emerald-600"
                            : p.result.trust_score >= 40 ? "text-amber-600"
                            : "text-rose-600"
                          }`}>
                            {p.result.trust_score}
                          </span>
                        )}
                        <Badge variant={statusVariant(p.status)} className="text-xs">
                          {statusLabel(p.status)}
                        </Badge>
                      </div>
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            </CardContent>
          </Card>
        </motion.div>
      </main>

      <footer className="max-w-6xl mx-auto px-6 py-8 text-xs text-muted-foreground text-center">
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <span>Passport Authority</span>
          <span className="text-slate-300">·</span>
          <span>Passport Observer</span>
          <span className="text-slate-300">·</span>
          <span>Security Probe</span>
          <span className="text-slate-300">·</span>
          <span>Compliance Agent</span>
          <span className="text-slate-300">·</span>
          <span>Capability Verifier</span>
        </div>
      </footer>
    </div>
  )
}
