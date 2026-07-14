import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel, ConfigDict
from typing import Optional, List

# Data storage directory setup
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data_storage"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "autosociety.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# SQLAlchemy setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==================== ORM Models ====================

class Citizen(Base):
    __tablename__ = "citizens"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    age = Column(Integer)
    job = Column(String)
    happiness = Column(Float, default=50.0)
    wealth = Column(Float, default=100.0)
    health = Column(Float, default=80.0)
    social_score = Column(Float, default=50.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorldState(Base):
    __tablename__ = "world_state"

    id = Column(Integer, primary_key=True, index=True)
    simulation_day = Column(Integer, default=0)
    total_wealth = Column(Float, default=0.0)
    avg_happiness = Column(Float, default=50.0)
    political_stability = Column(Float, default=50.0)
    economic_health = Column(Float, default=50.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    effects = Column(Text)  # JSON string of effects
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    owner_id = Column(Integer)  # citizen_id
    industry = Column(String)
    revenue = Column(Float, default=0.0)
    employees = Column(Integer, default=0)
    health = Column(Float, default=100.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text)
    event_type = Column(String)  # e.g., "disaster", "celebration", "political"
    affected_citizens = Column(String)  # JSON string of citizen IDs
    severity = Column(Integer, default=1)  # 1-10 scale
    created_at = Column(DateTime, default=datetime.utcnow)


class SimulationLog(Base):
    __tablename__ = "simulation_logs"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Integer)
    action = Column(String)
    agent_id = Column(Integer)  # citizen_id
    details = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


# ==================== Pydantic Schemas ====================

class CitizenBase(BaseModel):
    name: str
    age: int
    job: str
    happiness: float = 50.0
    wealth: float = 100.0
    health: float = 80.0
    social_score: float = 50.0


class CitizenCreate(CitizenBase):
    pass


class CitizenRead(CitizenBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WorldStateCreate(BaseModel):
    simulation_day: int = 0
    total_wealth: float = 0.0
    avg_happiness: float = 50.0
    political_stability: float = 50.0
    economic_health: float = 50.0


class WorldStateRead(WorldStateCreate):
    id: int
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PolicyCreate(BaseModel):
    name: str
    description: str
    effects: str


class PolicyRead(PolicyCreate):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BusinessCreate(BaseModel):
    name: str
    owner_id: int
    industry: str
    revenue: float = 0.0
    employees: int = 0


class BusinessRead(BusinessCreate):
    id: int
    health: float
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== Database Initialization ====================

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Get a database session."""
    return SessionLocal()


# ==================== CRUD Functions ====================

def create_citizen(session: Session, citizen: CitizenCreate) -> Citizen:
    """Create a new citizen."""
    db_citizen = Citizen(**citizen.model_dump())
    session.add(db_citizen)
    session.commit()
    session.refresh(db_citizen)
    return db_citizen


def get_citizen(session: Session, citizen_id: int) -> Optional[Citizen]:
    """Get a citizen by ID."""
    return session.query(Citizen).filter(Citizen.id == citizen_id).first()


def get_citizen_by_name(session: Session, name: str) -> Optional[Citizen]:
    """Get a citizen by name."""
    return session.query(Citizen).filter(Citizen.name == name).first()


def list_citizens(session: Session, skip: int = 0, limit: int = 100) -> List[Citizen]:
    """List all citizens with pagination."""
    return session.query(Citizen).offset(skip).limit(limit).all()


def update_citizen(session: Session, citizen_id: int, citizen_update: dict) -> Optional[Citizen]:
    """Update a citizen's attributes."""
    db_citizen = get_citizen(session, citizen_id)
    if db_citizen:
        for key, value in citizen_update.items():
            if hasattr(db_citizen, key):
                setattr(db_citizen, key, value)
        db_citizen.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(db_citizen)
    return db_citizen


def delete_citizen(session: Session, citizen_id: int) -> bool:
    """Delete a citizen."""
    db_citizen = get_citizen(session, citizen_id)
    if db_citizen:
        session.delete(db_citizen)
        session.commit()
        return True
    return False


def count_citizens(session: Session) -> int:
    """Count total citizens."""
    return session.query(Citizen).count()


# ==================== WorldState CRUD ====================

def get_or_create_world_state(session: Session) -> WorldState:
    """Get or create the singleton world state."""
    world = session.query(WorldState).first()
    if not world:
        world = WorldState()
        session.add(world)
        session.commit()
        session.refresh(world)
    return world


def update_world_state(session: Session, update_data: dict) -> WorldState:
    """Update world state."""
    world = get_or_create_world_state(session)
    for key, value in update_data.items():
        if hasattr(world, key):
            setattr(world, key, value)
    world.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(world)
    return world


# ==================== Policy CRUD ====================

def create_policy(session: Session, policy: PolicyCreate) -> Policy:
    """Create a new policy."""
    db_policy = Policy(**policy.model_dump())
    session.add(db_policy)
    session.commit()
    session.refresh(db_policy)
    return db_policy


def list_policies(session: Session) -> List[Policy]:
    """List all policies."""
    return session.query(Policy).all()


def get_policy(session: Session, policy_id: int) -> Optional[Policy]:
    """Get a policy by ID."""
    return session.query(Policy).filter(Policy.id == policy_id).first()


# ==================== Business CRUD ====================

def create_business(session: Session, business: BusinessCreate) -> Business:
    """Create a new business."""
    db_business = Business(**business.model_dump())
    session.add(db_business)
    session.commit()
    session.refresh(db_business)
    return db_business


def list_businesses(session: Session) -> List[Business]:
    """List all businesses."""
    return session.query(Business).all()


def get_business(session: Session, business_id: int) -> Optional[Business]:
    """Get a business by ID."""
    return session.query(Business).filter(Business.id == business_id).first()


# ==================== Event CRUD ====================

def create_event(session: Session, description: str, event_type: str, severity: int = 1) -> Event:
    """Create a new event."""
    event = Event(description=description, event_type=event_type, severity=severity)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
