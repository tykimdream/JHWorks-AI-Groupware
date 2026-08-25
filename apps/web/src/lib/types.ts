export type EmployeeRole = 'EMPLOYEE' | 'MANAGER' | 'POLICY_OWNER';
export type ApprovalType = 'GENERAL' | 'BUSINESS_TRIP' | 'LEAVE';
export type ApprovalStatus = 'DRAFT' | 'PENDING' | 'APPROVED' | 'REJECTED';
export type ApprovalLineStatus = 'WAITING' | 'PENDING' | 'APPROVED' | 'REJECTED';

export interface Department {
  id: string;
  name: string;
  parentDepartmentId: string | null;
  managerEmployeeId: string | null;
  isActive: boolean;
}

export interface EmployeeSummary {
  id: string;
  name: string;
  email: string;
  departmentId: string;
  position: string;
  role: EmployeeRole;
}

export interface CurrentEmployee extends EmployeeSummary {
  hireDate: string;
  leaveBalance: string;
  manager: EmployeeSummary | null;
  department: Department;
}

export interface AttachmentMetadata {
  name: string;
  contentType: string;
}

export interface GeneralDetails {
  kind: 'GENERAL';
}

export interface CostBreakdown {
  transportation: number | null;
  lodging: number | null;
  meals: number | null;
  other: number | null;
}

export interface BusinessTripDetails {
  kind: 'BUSINESS_TRIP';
  destination: string | null;
  startDate: string | null;
  endDate: string | null;
  costBreakdown: CostBreakdown | null;
  clientName: string | null;
  visitPurpose: string | null;
}

export type LeaveUnit = 'FULL_DAY' | 'HALF_DAY_AM' | 'HALF_DAY_PM';

export interface LeaveDetails {
  kind: 'LEAVE';
  leaveType: 'ANNUAL';
  leaveUnit: LeaveUnit;
  startDate: string | null;
  endDate: string | null;
  requestedDays: string | null;
  reason: string | null;
  handoverNote: string | null;
}

export type ApprovalDetails = GeneralDetails | BusinessTripDetails | LeaveDetails;

export interface ApprovalLine {
  id: string;
  step: number;
  round: number;
  approver: EmployeeSummary;
  status: ApprovalLineStatus;
  comment: string | null;
  actedAt: string | null;
}

export interface Approval {
  id: string;
  type: ApprovalType;
  title: string;
  content: string;
  author: EmployeeSummary;
  status: ApprovalStatus;
  amount: number | null;
  details: ApprovalDetails;
  attachmentMetadata: AttachmentMetadata[];
  version: number;
  submittedAt: string | null;
  decidedAt: string | null;
  createdAt: string;
  updatedAt: string;
  lines: ApprovalLine[];
}

export interface ApprovalListResponse {
  items: Approval[];
  total: number;
}

export interface ApprovalDraftInput {
  type: ApprovalType;
  title: string;
  content: string;
  amount: number | null;
  details: ApprovalDetails;
  attachmentMetadata: AttachmentMetadata[];
  version?: number;
}

export type ReviewStatus = 'PASS' | 'NEEDS_REVISION';
export type ReviewSource = 'DETERMINISTIC' | 'LLM' | 'POLICY';
export type ReviewSeverity = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH';
export type ReviewCategory = 'COMPLETENESS' | 'CLARITY' | 'WRITING' | 'RISK' | 'POLICY';
export type PolicyType = 'TRAVEL' | 'EXPENSE' | 'LEAVE' | 'APPROVAL' | 'SECURITY';
export type PolicyRetrievalStatus = 'READY' | 'NOT_APPLICABLE' | 'NOT_INDEXED' | 'UNAVAILABLE';
export type ReviewField =
  | 'document'
  | 'title'
  | 'content'
  | 'amount'
  | 'details.destination'
  | 'details.startDate'
  | 'details.endDate'
  | 'details.costBreakdown'
  | 'details.clientName'
  | 'details.visitPurpose'
  | 'details.leaveType'
  | 'details.leaveUnit'
  | 'details.requestedDays'
  | 'details.reason'
  | 'details.handoverNote'
  | 'attachmentMetadata';

export interface AIReviewIssue {
  code: string;
  source: ReviewSource;
  severity: ReviewSeverity;
  category: ReviewCategory;
  field: ReviewField;
  message: string;
  suggestion: string | null;
  citations: PolicyCitation[];
}

export interface PolicyCitation {
  citationKey: string;
  policyId: string;
  policyTitle: string;
  policyType: PolicyType;
  version: string;
  sectionId: string;
  sectionTitle: string;
  excerpt: string;
  similarityScore: number;
}

export interface PolicyEmbeddingUsage {
  inputTokens: number;
  totalTokens: number;
}

export interface PolicyReviewMetadata {
  status: PolicyRetrievalStatus;
  retrievedCitations: PolicyCitation[];
  provider: string | null;
  model: string | null;
  usage: PolicyEmbeddingUsage;
  latencyMs: number;
}

export interface PolicySearchResponse {
  status: PolicyRetrievalStatus;
  items: PolicyCitation[];
  provider: string | null;
  model: string | null;
  usage: PolicyEmbeddingUsage;
  latencyMs: number;
}

export interface AIReviewUsage {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
}

export interface AIReview {
  approvalId: string;
  approvalVersion: number;
  currentApprovalVersion: number;
  isStale: boolean;
  status: ReviewStatus;
  score: number;
  issues: AIReviewIssue[];
  revisedContent: string;
  provider: string;
  model: string;
  promptVersion: string;
  usage: AIReviewUsage;
  policyReview: PolicyReviewMetadata;
  latencyMs: number;
  reviewedAt: string;
}

export type ApprovalDraftIntent =
  | 'GENERAL'
  | 'BUSINESS_TRIP'
  | 'EXPENSE'
  | 'LEAVE'
  | 'UNSUPPORTED';
export type ApprovalDraftAIStatus = 'NEEDS_INPUT' | 'PREVIEW' | 'UNSUPPORTED';

export interface ApprovalDraftCandidate {
  intent: ApprovalDraftIntent;
  title: string | null;
  content: string | null;
  amount: number | null;
  destination: string | null;
  startDate: string | null;
  endDate: string | null;
  transportation: number | null;
  lodging: number | null;
  meals: number | null;
  other: number | null;
  clientName: string | null;
  visitPurpose: string | null;
}

export interface ApprovalDraftQuestion {
  field: string;
  prompt: string;
}

export interface ApprovalDraftPrepareResponse {
  status: ApprovalDraftAIStatus;
  assistantMessage: string;
  candidate: ApprovalDraftCandidate;
  missingFields: string[];
  questions: ApprovalDraftQuestion[];
  preview: ApprovalDraftInput | null;
  confirmationToken: string | null;
  policyContext: PolicySearchResponse;
  provider: string;
  model: string;
  promptVersion: string;
  usage: AIReviewUsage;
  latencyMs: number;
  generatedAt: string;
}

export interface WorkAssistantToolExecution {
  name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
}

export interface WorkAssistantResponse {
  answer: string;
  toolExecutions: WorkAssistantToolExecution[];
  policyCitations: PolicyCitation[];
  provider: string;
  model: string;
  promptVersion: string;
  roundCount: number;
  usage: AIReviewUsage;
  latencyMs: number;
  answeredAt: string;
}

export type AttendanceImpact = 'NONE' | 'CAUTION' | 'BLOCKED';
export type LeaveAvailabilityStatus =
  | 'READY'
  | 'NO_CANDIDATE'
  | 'INSUFFICIENT_BALANCE'
  | 'ACCOUNT_UNAVAILABLE';
export type LeaveCandidateStatus = 'AVAILABLE' | 'CAUTION';
export type LeaveAvailabilityReasonCode =
  | 'NO_CONFLICT'
  | 'WEEKEND'
  | 'HOLIDAY'
  | 'COMPANY_EVENT'
  | 'PROJECT_MILESTONE'
  | 'TEAM_LEAVE'
  | 'OWN_LEAVE'
  | 'INSUFFICIENT_BALANCE'
  | 'ACCOUNT_UNAVAILABLE'
  | 'NO_CANDIDATE';

export interface LeaveBalance {
  year: number;
  grantedDays: string;
  carriedOverDays: string;
  usedDays: string;
  pendingDays: string;
  availableDays: string;
  version: number;
  updatedAt: string;
}

export interface LeaveAvailabilityReason {
  code: LeaveAvailabilityReasonCode;
  impact: AttendanceImpact;
  message: string;
  eventIds: string[];
}

export interface LeaveAvailabilityDay {
  date: string;
  isWorkday: boolean;
  isSelectable: boolean;
  reasons: LeaveAvailabilityReason[];
}

export interface LeaveAvailabilityCandidate {
  startDate: string;
  endDate: string;
  workDates: string[];
  requestedDays: string;
  status: LeaveCandidateStatus;
  reasons: LeaveAvailabilityReason[];
}

export interface LeaveAvailability {
  status: LeaveAvailabilityStatus;
  rangeStart: string;
  rangeEnd: string;
  requestedDays: string;
  leaveBalance: LeaveBalance | null;
  candidates: LeaveAvailabilityCandidate[];
  days: LeaveAvailabilityDay[];
  reasons: LeaveAvailabilityReason[];
}

export type LeaveAssistantIntent = 'CHECK_DATES' | 'RECOMMEND_DATES' | 'UNSUPPORTED';
export type LeaveAssistantStatus = 'NEEDS_INPUT' | 'READY' | 'UNSUPPORTED';

export interface LeaveAssistantQuestion {
  field: string;
  prompt: string;
}

export interface LeaveAssistantQuery {
  intent: LeaveAssistantIntent;
  searchStart: string | null;
  searchEnd: string | null;
  requestedDays: string | null;
}

export interface LeaveAssistantResponse {
  status: LeaveAssistantStatus;
  assistantMessage: string;
  query: LeaveAssistantQuery;
  missingFields: string[];
  questions: LeaveAssistantQuestion[];
  availability: LeaveAvailability | null;
  policyContext: PolicySearchResponse;
  provider: string;
  model: string;
  promptVersion: string;
  usage: AIReviewUsage;
  latencyMs: number;
  generatedAt: string;
}

export interface LeaveDraftApprover {
  id: string;
  name: string;
  position: string;
}

export interface LeaveDraftExactPreview {
  approval: ApprovalDraftInput;
  candidate: LeaveAvailabilityCandidate;
  requestedDays: string;
  leaveUnit: LeaveUnit;
  availableDays: string;
  accountVersion: number;
  manager: LeaveDraftApprover;
  policyContext: PolicySearchResponse;
  warnings: LeaveAvailabilityReason[];
  calendarFingerprint: string;
  policyFingerprint: string;
}

export interface LeaveDraftPrepareResponse {
  preview: LeaveDraftExactPreview;
  confirmationToken: string;
}

export type LeaveAgentStatus =
  | 'CONSULTING'
  | 'NEEDS_INPUT'
  | 'CONSULTATION_FAILED'
  | 'CANDIDATES_READY'
  | 'AWAITING_DRAFT_CONFIRMATION'
  | 'DRAFT_CREATED'
  | 'AWAITING_SUBMIT_CONFIRMATION'
  | 'SUBMITTING'
  | 'SUBMITTED'
  | 'CANCELED'
  | 'EXPIRED'
  | 'STALE'
  | 'FAILED';

export interface LeaveAgentTrace {
  at: string;
  fromStatus: LeaveAgentStatus | null;
  toStatus: LeaveAgentStatus;
  event: string;
  resultCode: string;
}

export interface LeaveAgentRun {
  id: string;
  status: LeaveAgentStatus;
  approvalId: string | null;
  retryCount: number;
  lastErrorCode: string | null;
  version: number;
  trace: LeaveAgentTrace[];
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
}

export interface LeaveAgentConsultation {
  run: LeaveAgentRun;
  consultation: LeaveAssistantResponse | null;
}

export interface LeaveAgentDraftPreparation {
  run: LeaveAgentRun;
  preparation: LeaveDraftPrepareResponse;
}

export interface LeaveAgentDraftConfirmation {
  run: LeaveAgentRun;
  approval: Approval;
}

export interface LeaveSubmitPreview {
  approvalId: string;
  approvalVersion: number;
  requestedDays: string;
  availableDays: string;
  pendingDays: string;
  accountVersion: number;
  managerId: string;
  managerName: string;
  managerPosition: string;
  warnings: LeaveAvailabilityReason[];
  calendarFingerprint: string;
}

export interface LeaveSubmitPreparation {
  run: LeaveAgentRun;
  preview: LeaveSubmitPreview;
  confirmationToken: string;
  expiresAt: string;
}

export interface LeaveSubmitResumeResult {
  run: LeaveAgentRun;
  approval: Approval;
}
