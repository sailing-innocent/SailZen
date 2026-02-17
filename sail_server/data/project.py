from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB
from .orm import ORMBase
from sqlalchemy.orm import relationship
from sail_server.utils.time_utils import QuarterBiWeekTime
from sail_server.utils.money import Money
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
import json
from typing import Any
from msgspec import Struct

LAST_TIMESTAMP_LIFE = date(2199, 1, 1)
MINIMUM_TIME_REQUIREMENT = timedelta(minutes=20)  # 20 minutes


# -----------------------------------------
# Long-Term Project Management
# -----------------------------------------
class Project(ORMBase):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    state = Column(Integer)  # Project State
    start_time = Column(Integer)  # QBWTime
    end_time = Column(Integer)  # QBWTime
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())


class ProjectState:
    # Project State Machine
    # -----------------------------------------------------
    # INVALID -> VALID -> PREPARE -> TRACKING ---> DONE
    #                                  ^   |
    #                                  |   v
    #                                  PENDING---> CANCEL
    # ------------------------------------------------------
    # state enum
    INVALID = 0
    VALID = 1
    PREPARE = 2
    TRACKING = 3
    DONE = 4
    PENDING = 5
    CANCELED = 6
    _state = INVALID

    def __init__(self, state: int = INVALID):
        self._state = state

    def valid(self):
        self._state = self.VALID

    def prepare(self):
        if self._state == self.VALID:
            self._state = self.PREPARE
        else:
            raise ValueError("Invalid state for prepare")

    def tracking(self):
        if self._state == self.PREPARE:
            self._state = self.TRACKING
        else:
            raise ValueError("Invalid state for tracking")

    def pending(self):
        if self._state == self.TRACKING:
            self._state = self.PENDING
        else:
            raise ValueError("Invalid state for pending")

    def restore(self):
        if self._state == self.PENDING:
            self._state = self.TRACKING
        else:
            raise ValueError("Invalid state for restore")

    def done(self):
        if self._state == self.PENDING:
            self._state = self.DONE
        else:
            raise ValueError("Invalid state for done")

    def cancel(self):
        # no need to check state
        self._state = self.CANCELED

    def get_state(self) -> int:
        return self._state


@dataclass
class ProjectData:
    """
    The Project Data
    """

    id: int = field(default=None)
    name: str = field(default="")
    description: str = field(default="")
    state: int = field(default_factory=lambda: ProjectState().get_state())
    # Project Start and End Time is QuarterBiWeekTime
    start_time: int = field(
        default_factory=lambda: QuarterBiWeekTime.from_datetime(
            datetime.now()
        ).to_db_int()
    )
    end_time: int = field(
        default_factory=lambda: QuarterBiWeekTime.from_datetime(
            datetime.now() + timedelta(days=14)
        ).to_db_int()
    )
    ctime: datetime = field(default_factory=lambda: datetime.now())
    mtime: datetime = field(default_factory=lambda: datetime.now())

    @classmethod
    def read_from_orm(cls, orm: Project):
        return cls(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            state=orm.state,
            start_time=orm.start_time,
            end_time=orm.end_time,
            ctime=orm.ctime,
            mtime=orm.mtime,
        )

    @classmethod
    def from_dict(cls, json_data: dict):
        return cls(
            id=json_data.get("id"),
            name=json_data.get("name"),
            description=json_data.get("description"),
            state=json_data.get("state"),
            start_time=json_data.get("start_time"),
            end_time=json_data.get("end_time"),
            ctime=json_data.get("ctime"),
            mtime=json_data.get("mtime"),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "state": self.state,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "ctime": self.ctime,
            "mtime": self.mtime,
        }

    @classmethod
    def from_string(cls, project_str: str):
        return cls.from_dict(json.loads(project_str))

    def to_string(self):
        return json.dumps(self.to_dict())

    def create_project(self):
        return Project(
            name=self.name,
            description=self.description,
            start_time=self.start_time,
            end_time=self.end_time,
        )

    def update_project(self, project: Project):
        project.name = self.name
        project.description = self.description
        project.start_time = self.start_time
        project.end_time = self.end_time
        project.mtime = datetime.now()


# -----------------------------------------
# Mission Management in Tree Structure (left-right structure)
# -----------------------------------------
class Mission(ORMBase):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True)
    # basic Mission info
    name = Column(String)
    description = Column(String)
    parent_id = Column(
        Integer, ForeignKey("missions.id"), nullable=True, default=None
    )  # parent node id, null means no parent required
    state = Column(Integer)  # 0: pending 1: ready 2: doing 3: done 4: cancel
    ddl = Column(TIMESTAMP)  # deadline in timestamp in seconds
    project_id = Column(
        Integer, ForeignKey("projects.id"), nullable=True, default=None
    )  # project id, null means no project

    # end basic Mission info

    # Internal use only, do not use in query
    # --------------------------------------
    # 在构建树结构时我们只会指定parent_id，执行查找前会检查距离上一个checkpoint之间是否有插入/删除操作，如果有，需要刷新lft和rgt
    # 辅助前序遍历方法，如果A节点是B节点的父节点，则A节点的lft小于B节点的lft，A节点的rgt大于B节点的rgt
    lft = Column(Integer)
    rgt = Column(Integer)
    tree_id = Column(Integer)  # tree id, used for differentiate different trees
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    # end internal use only


class MissionState:
    # Mission State Machine
    # -----------------------------------------------------
    # PENDING -> READY -> DOING ---> DONE
    #  ^                  |    |
    #  |                  |    v
    #  <------------------    CANCEL
    # ------------------------------------------------------
    PENDING = 0
    READY = 1
    DOING = 2
    DONE = 3
    CANCELED = 4

    def __init__(self, state: int = PENDING):
        self._state = state

    def pending(self):
        self._state = self.PENDING

    def ready(self):
        self._state = self.READY

    def doing(self):
        self._state = self.DOING

    def done(self):
        self._state = self.DONE

    def cancel(self):
        self._state = self.CANCELED

    def get_state(self) -> int:
        return self._state


@dataclass
class MissionData:
    id: int = field(default=None)
    name: str = field(default="")
    description: str = field(default="")
    parent_id: int = field(default=0)
    project_id: int = field(default=0)
    state: int = field(default_factory=lambda: MissionState().get_state())
    ctime: datetime = field(default_factory=lambda: datetime.now())
    mtime: datetime = field(default_factory=lambda: datetime.now())
    ddl: datetime = field(
        default_factory=lambda: datetime.now() + timedelta(days=14)
    )  # two weeks by default

    @classmethod
    def read_from_orm(cls, orm: Mission):
        return cls(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            parent_id=orm.parent_id,
            project_id=orm.project_id,
            state=orm.state,
            ctime=orm.ctime,
            mtime=orm.mtime,
            ddl=orm.ddl,
        )

    def create_mission(self):
        parent_id = self.parent_id if self.parent_id > 0 else None
        project_id = self.project_id if self.project_id > 0 else None
        return Mission(
            name=self.name,
            description=self.description,
            parent_id=parent_id,
            project_id=project_id,
            state=self.state,
            ddl=self.ddl,
        )

    @classmethod
    def from_dict(cls, json_data: dict):
        return cls(
            id=json_data.get("id"),
            name=json_data.get("name"),
            description=json_data.get("description"),
            parent_id=json_data.get("parent_id"),
            project_id=json_data.get("project_id"),
            state=json_data.get("state"),
            ctime=json_data.get("ctime"),
            mtime=json_data.get("mtime"),
            ddl=json_data.get("ddl"),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "project_id": self.project_id,
            "state": self.state.get_state(),
            "ctime": self.ctime,
            "mtime": self.mtime,
            "ddl": self.ddl,
        }
