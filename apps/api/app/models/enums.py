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
