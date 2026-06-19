export type Passport = {
  request_id: string
  agent_name: string
  submitted_context: string
  requested_permissions: string[]
  status: "pending" | "approved" | "rejected" | "conditional_approval"
  result: {
    passport_id: string
    status: string
    trust_score: number
    approved_permissions: string[]
    blocked_permissions: string[]
    rationale: string
  } | null
  submitted_at: string
  decided_at: string | null
}

export async function submitPassport(
  agent_name: string,
  submitted_context: string,
  requested_permissions: string[],
): Promise<Passport> {
  const r = await fetch("/passport", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_name, submitted_context, requested_permissions }),
  })
  if (!r.ok) throw new Error(`submit failed: ${r.status}`)
  return r.json()
}

export async function getPassport(request_id: string): Promise<Passport> {
  const r = await fetch(`/passport/${request_id}`)
  if (!r.ok) throw new Error(`get failed: ${r.status}`)
  return r.json()
}

export async function listPassports(): Promise<Passport[]> {
  const r = await fetch("/passports")
  if (!r.ok) return []
  return r.json()
}
