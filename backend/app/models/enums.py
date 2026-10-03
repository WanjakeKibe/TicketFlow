from enum import Enum


class UserRole(str, Enum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    AGENT = "AGENT"


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketEventType(str, Enum):
    CREATED = "CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ASSIGNMENT_CHANGED = "ASSIGNMENT_CHANGED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    CATEGORY_CHANGED = "CATEGORY_CHANGED"
    COMMENT_ADDED = "COMMENT_ADDED"
