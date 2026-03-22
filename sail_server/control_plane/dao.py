from sqlalchemy.orm import Session

from sail_server.control_plane.models import (
    EdgeNode,
    InteractionThread,
    OpenCodeSession,
    RemoteWorkspace,
    SessionAction,
    SessionEvent,
)
from sail_server.data.dao.base import BaseDAO


class RemoteWorkspaceDAO(BaseDAO[RemoteWorkspace]):
    def __init__(self, db: Session):
        super().__init__(db, RemoteWorkspace)


class EdgeNodeDAO(BaseDAO[EdgeNode]):
    def __init__(self, db: Session):
        super().__init__(db, EdgeNode)


class OpenCodeSessionDAO(BaseDAO[OpenCodeSession]):
    def __init__(self, db: Session):
        super().__init__(db, OpenCodeSession)


class SessionActionDAO(BaseDAO[SessionAction]):
    def __init__(self, db: Session):
        super().__init__(db, SessionAction)


class SessionEventDAO(BaseDAO[SessionEvent]):
    def __init__(self, db: Session):
        super().__init__(db, SessionEvent)


class InteractionThreadDAO(BaseDAO[InteractionThread]):
    def __init__(self, db: Session):
        super().__init__(db, InteractionThread)
