export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "analyst" | "user" | string;
  is_active: boolean;
  is_verified?: boolean;
}

export interface CaseItem {
  id: string;
  case_number: string;
  title: string;
  category: string;
  description?: string | null;
  user_id: string;
  risk_level: string;
  status: string;
  urls: string[];
  notes?: string | null;
  created_at: string;
  updated_at: string;
  evidence_count?: number;
}

export interface EvidenceItem {
  id: string;
  case_id?: string | null;
  user_id: string;
  original_filename: string;
  file_size: number;
  mime_type: string;
  sha256_hash: string;
  evidence_type: string;
  description?: string | null;
  is_sensitive: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AnalysisFinding {
  category: string;
  severity: string;
  description: string;
  score: number;
  timestamp_start?: number;
  timestamp_end?: number;
}

export interface AnalysisEvidence {
  indicator: string;
  observed_value: unknown;
  interpretation: string;
}

export interface AnalysisResult {
  analysis_id: string;
  content_type: string;
  risk_level: string;
  confidence: number;
  findings: AnalysisFinding[];
  evidence: AnalysisEvidence[];
  explanation: string;
  limitations: string[];
  recommended_action: string;
  input_reference?: string | null;
  raw_metadata?: Record<string, unknown>;
  case_id?: string | null;
  created_at?: string;
}

export interface FingerprintItem {
  id: string;
  user_id: string;
  title: string;
  media_type: string;
  sha256_hash: string;
  phash?: string | null;
  dhash?: string | null;
  ahash?: string | null;
  description?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface FingerprintMatch {
  id: string;
  title: string;
  media_type: string;
  sha256_hash: string;
  phash?: string | null;
  similarity_score: number;
  hamming_distance: number;
  match_type: string;
  created_at: string;
}

export interface DuplicateMatchItem {
  id: string;
  source_id: string;
  matched_fingerprint_id: string;
  matched_title: string;
  similarity_score: number;
  match_type: string;
  details: Record<string, unknown>;
  detected_at: string;
}

export interface RemovalWorkflowItem {
  id: string;
  case_id: string;
  user_id: string;
  platform: string;
  violation_type: string;
  report_content: string;
  status: string;
  human_approved: boolean;
  approved_by?: string | null;
  approved_at?: string | null;
  submission_reference?: string | null;
  notes?: string | null;
  official_portal_url?: string | null;
  guidance_steps?: string[] | null;
  updated_at: string;
}

export interface ReportItem {
  id: string;
  case_id: string;
  user_id: string;
  template_type: string;
  title: string;
  summary: string;
  findings_snapshot: Record<string, unknown>;
  file_path?: string | null;
  status: string;
  created_at: string;
}

export interface NotificationItem {
  id: string;
  user_id: string;
  title: string;
  message: string;
  notification_type: string;
  is_read: boolean;
  case_id?: string | null;
  link?: string | null;
  created_at: string;
}

export interface SystemHealth {
  status: string;
  app_name: string;
  version: string;
  company: string;
  environment: string;
  database_status: string;
  ollama_status: string;
  redis_status: string;
  storage_accessible: boolean;
  active_cases: number;
  total_users: number;
  system_time: string;
}

export interface UserAdminItem {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  case_count: number;
}

export interface AIModelItem {
  id: string;
  model_name: string;
  provider: string;
  is_active: boolean;
  endpoint_url?: string | null;
  description?: string | null;
  updated_at: string;
}

export interface AuditLogItem {
  id: string;
  user_id?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  details: Record<string, unknown>;
  ip_address?: string | null;
  timestamp: string;
}

export interface DashboardStats {
  total_cases: number;
  content_analyzed: number;
  high_risk_cases: number;
  pending_reports: number;
  confirmed_removal_cases: number;
  cases_under_review: number;
  risk_distribution: Array<{ name: string; count: number; color: string }>;
  case_status_distribution: Array<{ status: string; count: number; label: string }>;
  recent_activities: Array<{
    id: string;
    action: string;
    description: string;
    timestamp: string;
    category: string;
    severity: string;
  }>;
  recent_analyses: Array<{
    id: string;
    content_type: string;
    risk_level: string;
    confidence: number;
    input_reference?: string | null;
    created_at: string;
  }>;
}
