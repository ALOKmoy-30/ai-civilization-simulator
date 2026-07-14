"""
Pytest suite for database.py
"""

import pytest
import os
from pathlib import Path
from datetime import datetime

from autosociety.backend.core.database import (
    init_db,
    get_session,
    create_citizen,
    get_citizen,
    get_citizen_by_name,
    list_citizens,
    update_citizen,
    delete_citizen,
    count_citizens,
    CitizenCreate,
    get_or_create_world_state,
    update_world_state,
    create_policy,
    PolicyCreate,
    create_business,
    BusinessCreate,
    create_event,
    DATABASE_URL,
    DB_PATH,
    engine,
)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    # Remove test DB if it exists
    if DB_PATH.exists():
        DB_PATH.unlink()

    init_db()
    session = get_session()
    yield session
    # Cleanup after test
    session.close()
    engine.dispose()  # Close all connections
    if DB_PATH.exists():
        DB_PATH.unlink()


def test_create_citizen(db_session):
    """Test creating a citizen."""
    citizen_data = CitizenCreate(
        name="John Doe",
        age=30,
        job="Engineer",
        happiness=75.0,
        wealth=150.0,
        health=85.0,
        social_score=60.0,
    )

    citizen = create_citizen(db_session, citizen_data)

    assert citizen.id is not None
    assert citizen.name == "John Doe"
    assert citizen.age == 30
    assert citizen.job == "Engineer"
    assert citizen.happiness == 75.0


def test_get_citizen(db_session):
    """Test retrieving a citizen by ID."""
    citizen_data = CitizenCreate(name="Jane Doe", age=28, job="Doctor")
    citizen = create_citizen(db_session, citizen_data)
    citizen_id = citizen.id

    retrieved = get_citizen(db_session, citizen_id)

    assert retrieved is not None
    assert retrieved.name == "Jane Doe"
    assert retrieved.job == "Doctor"


def test_get_citizen_by_name(db_session):
    """Test retrieving a citizen by name."""
    citizen_data = CitizenCreate(name="Alice Smith", age=35, job="Lawyer")
    create_citizen(db_session, citizen_data)

    retrieved = get_citizen_by_name(db_session, "Alice Smith")

    assert retrieved is not None
    assert retrieved.name == "Alice Smith"
    assert retrieved.job == "Lawyer"


def test_list_citizens(db_session):
    """Test listing all citizens."""
    for i in range(5):
        citizen_data = CitizenCreate(
            name=f"Citizen {i}",
            age=20 + i,
            job=f"Job {i}",
        )
        create_citizen(db_session, citizen_data)

    citizens = list_citizens(db_session)

    assert len(citizens) == 5


def test_update_citizen(db_session):
    """Test updating a citizen."""
    citizen_data = CitizenCreate(
        name="Bob Wilson",
        age=40,
        job="Manager",
        happiness=50.0,
    )
    citizen = create_citizen(db_session, citizen_data)
    citizen_id = citizen.id

    updated = update_citizen(
        db_session,
        citizen_id,
        {"happiness": 80.0, "wealth": 200.0},
    )

    assert updated.happiness == 80.0
    assert updated.wealth == 200.0


def test_delete_citizen(db_session):
    """Test deleting a citizen."""
    citizen_data = CitizenCreate(name="ToDelete", age=25, job="Temp")
    citizen = create_citizen(db_session, citizen_data)
    citizen_id = citizen.id

    deleted = delete_citizen(db_session, citizen_id)
    assert deleted is True
    retrieved = get_citizen(db_session, citizen_id)

    assert retrieved is None


def test_count_citizens(db_session):
    """Test counting citizens."""
    for i in range(3):
        citizen_data = CitizenCreate(name=f"Count {i}", age=30, job="Job")
        create_citizen(db_session, citizen_data)

    count = count_citizens(db_session)

    assert count == 3


def test_world_state(db_session):
    """Test world state get/create and update."""
    world = get_or_create_world_state(db_session)
    assert world.id is not None
    assert world.simulation_day == 0

    updated = update_world_state(
        db_session,
        {"simulation_day": 5, "avg_happiness": 65.0},
    )
    assert updated.simulation_day == 5
    assert updated.avg_happiness == 65.0


def test_create_policy(db_session):
    """Test creating a policy."""
    policy_data = PolicyCreate(
        name="Tax Reform",
        description="A progressive tax policy",
        effects='{"wealth": -10}',
    )
    policy = create_policy(db_session, policy_data)

    assert policy.id is not None
    assert policy.name == "Tax Reform"
    assert policy.is_active is True


def test_create_business(db_session):
    """Test creating a business."""
    business_data = BusinessCreate(
        name="TechCorp",
        owner_id=1,
        industry="Technology",
        revenue=50000.0,
        employees=10,
    )
    business = create_business(db_session, business_data)

    assert business.id is not None
    assert business.name == "TechCorp"
    assert business.owner_id == 1


def test_create_event(db_session):
    """Test creating an event."""
    event = create_event(
        db_session,
        description="A major storm hit the city",
        event_type="disaster",
        severity=8,
    )

    assert event.id is not None
    assert event.event_type == "disaster"
    assert event.severity == 8
