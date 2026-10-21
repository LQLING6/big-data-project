export interface User { id: number; username: string; role: string }
export interface Profile {
  major: string; school: string; level: string; grade: number | null
  skills: string[]; interests: string[]; weekly_hours: number | null
  unavailable_dates: string[]; version: number
}
export interface Competition {
  id: number; title: string; organizer: string; category: string; summary: string
  edition: string; tags: string[]; skill_tags: string[]; allowed_majors: string[]
  allowed_levels: string[]; allowed_school: string | null; grade_min: number | null
  grade_max: number | null; deadline_at: string | null; deadline_date: string | null
  deadline_precision: string; deadline_kind: string; event_date: string | null
  source_url: string; evidence: Record<string, { quote: string; origin: string }>
  status: string; review_status: string; version: number; is_demo: boolean
}
export interface Subscription { id: number; lead_hours: number; competition: Competition }
export interface Notification {
  id: number; title: string; body: string; kind: string; channel: string
  delivery_status: string; read: boolean; created_at: string
}
export interface Recommendation {
  competition: Competition; score: number; qualification: string
  reasons: { code: string; text: string; evidence_field: string | null }[]
  warnings: string[]; profile_version: number; competition_version: number
}
export interface Source {
  id: number; name: string; base_url: string; is_demo: boolean
  network_enabled: boolean; policy_status: string; interval_seconds: number
}
