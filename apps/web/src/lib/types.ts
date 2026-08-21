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

