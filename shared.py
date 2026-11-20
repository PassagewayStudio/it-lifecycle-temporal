"""Values shared by the worker, the starter script and the tests."""
from dataclasses import dataclass

TASK_QUEUE = "offboarding-task-queue"


@dataclass
class OffboardingParams:
    user_email: str
    device_serial: str
    # How long to wait for the laptop to come back before deleting the account.
    # Short by default so you can test quickly; in real life this would be days.
    device_return_wait_seconds: int = 30


@dataclass
class AccessRequestParams:
    user_email: str
    group_id: str  # Okta group that grants the access
    duration_seconds: int = 120  # how long the access lasts once approved
    approval_timeout_seconds: int = 300  # request expires if nobody decides in time
