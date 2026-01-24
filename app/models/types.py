"""공용 타입 정의"""

from typing import Literal

ConversionMode = Literal["pdf-to-md", "md-to-pdf"]
TaskStatus = Literal["pending", "processing", "completed", "failed"]
