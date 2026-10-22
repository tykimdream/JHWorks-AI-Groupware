from typing import Literal

from app.core.schema import ApiSchema
from app.schemas.employee import CurrentEmployeeRead


class DemoConfiguration(ApiSchema):
    enabled: bool
    duration_minutes: int
    write_limit: int = 20
    request_limit: int = 100


class DemoRoleRequest(ApiSchema):
    role: Literal["author", "manager"]


class DemoVisitRead(ApiSchema):
    employee: CurrentEmployeeRead
    expires_at_epoch: int
