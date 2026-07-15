"""
Script to seed the database with 30 dummy citizens using Faker.
Run with: python -m autosociety.scripts.seed_dummy_citizens
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from faker import Faker
from autosociety.backend.core.database import (
    init_db,
    get_session,
    create_citizen,
    CitizenCreate,
    count_citizens,
    Base as DBBase,
    engine as db_engine,
)
from autosociety.backend.core.metrics import MetricsBase, metrics_engine, init_metrics_db

fake = Faker()

# Job titles to randomly assign
JOBS = [
    "Engineer", "Teacher", "Doctor", "Nurse", "Lawyer", "Accountant",
    "Manager", "Chef", "Artist", "Writer", "Architect", "Electrician",
    "Plumber", "Carpenter", "Mechanic", "Pilot", "Scientist", "Researcher",
    "Software Developer", "Data Analyst", "Marketing Manager", "Sales Rep",
    "Consultant", "Analyst", "Designer", "Producer", "Administrator",
    "Technician", "Pharmacist", "Therapist"
]


def seed_citizens(num_citizens: int = 30):
    """Generate and insert dummy citizens into the database."""
    if "--append" in sys.argv:
        print(f"Appending {num_citizens} citizens without dropping existing tables...")
        init_db()
        init_metrics_db()
    else:
        print(f"Resetting database (dropping all tables)...")
        DBBase.metadata.drop_all(bind=db_engine)
        MetricsBase.metadata.drop_all(bind=metrics_engine)
        print(f"Creating fresh tables...")
        init_db()
        init_metrics_db()

    session = get_session()

    print(f"Seeding {num_citizens} dummy citizens...")
    created_count = 0

    for i in range(num_citizens):
        try:
            citizen_data = CitizenCreate(
                name=fake.unique.name(),
                age=fake.random_int(min=18, max=80),
                job=fake.random_element(JOBS),
                happiness=round(fake.random.uniform(20.0, 100.0), 2),
                wealth=round(fake.random.uniform(50.0, 500.0), 2),
                health=round(fake.random.uniform(40.0, 100.0), 2),
                social_score=round(fake.random.uniform(10.0, 100.0), 2),
            )

            citizen = create_citizen(session, citizen_data)
            created_count += 1
            if (i + 1) % 10 == 0:
                print(f"  Created {i + 1}/{num_citizens} citizens...")

        except Exception as e:
            print(f"  Error creating citizen {i + 1}: {e}")
            continue

    session.close()

    # Verify
    session = get_session()
    total = count_citizens(session)
    session.close()

    print(f"\nSuccess! Created {created_count} citizens.")
    print(f"Total citizens in database: {total}")


if __name__ == "__main__":
    seed_citizens(30)
