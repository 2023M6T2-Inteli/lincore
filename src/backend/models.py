from database import Base
from sqlalchemy import TIMESTAMP, Column, String, Integer, Float, Boolean
from sqlalchemy.sql import func
# from fastapi_utils.guid_type import GUID, GUID_DEFAULT_SQLITE
from uuid import UUID


class Report(Base):
    __tablename__ = 'report'
    id = Column(Integer, primary_key=True)
    projectName = Column(String, nullable=False)
    typePlace = Column(Integer)
    operator = Column(String)
    date = Column(TIMESTAMP)
    gasLevel1 = Column(Float)
    gasLevel2 = Column(Float)
    createdAt = Column(TIMESTAMP(timezone=True),
                       server_default=func.now())
    updatedAt = Column(TIMESTAMP(timezone=True),
                       default=None, onupdate=func.now())

