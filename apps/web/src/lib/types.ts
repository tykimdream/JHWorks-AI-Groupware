export type EmployeeRole = 'EMPLOYEE' | 'MANAGER' | 'POLICY_OWNER';
export type ApprovalType = 'GENERAL' | 'BUSINESS_TRIP';
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

export type ApprovalDetails = GeneralDetails | BusinessTripDetails;

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
  revisedContent: string | null;
  provider: string;
  model: string;
  promptVersion: string;
  usage: AIReviewUsage;
  policyReview: PolicyReviewMetadata;
  latencyMs: number;
  reviewedAt: string;
}
