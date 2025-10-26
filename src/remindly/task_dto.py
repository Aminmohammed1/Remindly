from sqlalchemy import create_engine, Column, BigInteger, String, Text, Boolean, TIMESTAMP, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Replace with your Supabase Postgres credentials
DATABASE_URL = "postgresql://<user>:<password>@<host>:5432/<database>"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

class UserTask(Base):
    __tablename__ = "UserTasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    phone_number = Column(String(20), nullable=False)
    task = Column(Text, nullable=False)
    created_at_timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now())
    trigger_timestamp = Column(TIMESTAMP(timezone=True), nullable=False)
    call_intent = Column(Boolean, default=False)

# Create table in DB
Base.metadata.create_all(bind=engine)
