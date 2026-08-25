from enum import StrEnum


class EmployeeRole(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    POLICY_OWNER = "POLICY_OWNER"


class ApprovalType(StrEnum):
    GENERAL = "GENERAL"
    BUSINESS_TRIP = "BUSINESS_TRIP"
    EXPENSE = "EXPENSE"
    LEAVE = "LEAVE"


class ApprovalStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalLineStatus(StrEnum):
    WAITING = "WAITING"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PolicyType(StrEnum):
    TRAVEL = "TRAVEL"
    EXPENSE = "EXPENSE"
    LEAVE = "LEAVE"
    APPROVAL = "APPROVAL"
    SECURITY = "SECURITY"


class PolicyStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AttendanceEventCategory(StrEnum):
    COMPANY_EVENT = "COMPANY_EVENT"
    PROJECT_MILESTONE = "PROJECT_MILESTONE"
    HOLIDAY = "HOLIDAY"
    LEAVE = "LEAVE"


class AttendanceEventScope(StrEnum):
    COMPANY = "COMPANY"
    DEPARTMENT = "DEPARTMENT"
    EMPLOYEE = "EMPLOYEE"


class AttendanceEventStatus(StrEnum):
    TENTATIVE = "TENTATIVE"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"


class AttendanceImpact(StrEnum):
    NONE = "NONE"
    CAUTION = "CAUTION"
    BLOCKED = "BLOCKED"


class LeaveAvailabilityStatus(StrEnum):
    READY = "READY"
    NO_CANDIDATE = "NO_CANDIDATE"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    ACCOUNT_UNAVAILABLE = "ACCOUNT_UNAVAILABLE"


class LeaveCandidateStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    CAUTION = "CAUTION"


class LeaveAvailabilityReasonCode(StrEnum):
    NO_CONFLICT = "NO_CONFLICT"
    WEEKEND = "WEEKEND"
    HOLIDAY = "HOLIDAY"
    COMPANY_EVENT = "COMPANY_EVENT"
    PROJECT_MILESTONE = "PROJECT_MILESTONE"
    TEAM_LEAVE = "TEAM_LEAVE"
    OWN_LEAVE = "OWN_LEAVE"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    ACCOUNT_UNAVAILABLE = "ACCOUNT_UNAVAILABLE"
    NO_CANDIDATE = "NO_CANDIDATE"
