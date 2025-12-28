from __future__ import annotations

from app.db.database import Base, engine
from app.db import models  # noqa: F401  (import to register models)

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
