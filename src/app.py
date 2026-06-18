"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


current_dir = Path(__file__).parent
DATABASE_URL = f"sqlite:///{current_dir / 'school.db'}"

# check_same_thread=False is required so FastAPI request workers can share the SQLite connection pool.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (CheckConstraint("max_participants > 0", name="ck_activity_max_participants_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str] = mapped_column(String)
    schedule: Mapped[str] = mapped_column(String(255))
    max_participants: Mapped[int] = mapped_column()
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    registrations: Mapped[list["Registration"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan",
    )
    complaints: Mapped[list["Complaint"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan",
    )


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("activity_id", "student_email", name="uq_registration_activity_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), index=True)
    student_email: Mapped[str] = mapped_column(String(320), index=True)

    activity: Mapped[Activity] = relationship(back_populates="registrations")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(50), default="student", index=True)

    complaints: Mapped[list["Complaint"]] = relationship(back_populates="student")
    authored_responses: Mapped[list["ComplaintResponse"]] = relationship(back_populates="admin")


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id", ondelete="RESTRICT"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)

    activity: Mapped[Activity] = relationship(back_populates="complaints")
    student: Mapped[User] = relationship(back_populates="complaints")
    responses: Mapped[list["ComplaintResponse"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
    )


class ComplaintResponse(Base):
    __tablename__ = "complaint_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), index=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    message: Mapped[str] = mapped_column(String)

    complaint: Mapped[Complaint] = relationship(back_populates="responses")
    admin: Mapped[User] = relationship(back_populates="authored_responses")


SEED_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"],
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
    },
}


def get_or_create_user(session: Session, email: str, role: str = "student") -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(email=email, role=role)
    session.add(user)
    session.flush()
    return user


def seed_data(session: Session) -> None:
    existing_activity = session.scalar(select(Activity.id).limit(1))
    if existing_activity is not None:
        return

    for name, details in SEED_ACTIVITIES.items():
        activity = Activity(
            name=name,
            description=details["description"],
            schedule=details["schedule"],
            max_participants=details["max_participants"],
            category=None,
        )
        session.add(activity)
        session.flush()

        for email in details["participants"]:
            get_or_create_user(session, email)
            session.add(Registration(activity_id=activity.id, student_email=email))

    session.commit()


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_data(session)
    yield

app = FastAPI(
    title="Mergington High School API",
    description="API for viewing and signing up for extracurricular activities",
    lifespan=lifespan,
)

# Mount the static files directory
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(Path(__file__).parent, "static")),
    name="static",
)


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities(session: Session = Depends(get_session)):
    db_activities = session.scalars(select(Activity).order_by(Activity.name.asc())).all()

    activity_response = {}
    for activity in db_activities:
        activity_response[activity.name] = {
            "description": activity.description,
            "schedule": activity.schedule,
            "max_participants": activity.max_participants,
            "participants": [registration.student_email for registration in activity.registrations],
        }

    return activity_response


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, session: Session = Depends(get_session)):
    """Sign up a student for an activity"""
    activity = session.scalar(select(Activity).where(Activity.name == activity_name))
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    if len(activity.registrations) >= activity.max_participants:
        raise HTTPException(status_code=400, detail="Activity is full")

    existing_registration = session.scalar(
        select(Registration).where(
            Registration.activity_id == activity.id,
            Registration.student_email == email,
        )
    )
    if existing_registration is not None:
        raise HTTPException(status_code=400, detail="Student is already signed up")

    get_or_create_user(session, email)
    session.add(Registration(activity_id=activity.id, student_email=email))

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Student is already signed up") from exc

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, session: Session = Depends(get_session)):
    """Unregister a student from an activity"""
    activity = session.scalar(select(Activity).where(Activity.name == activity_name))
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    registration = session.scalar(
        select(Registration).where(
            Registration.activity_id == activity.id,
            Registration.student_email == email,
        )
    )
    if registration is None:
        raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

    session.delete(registration)
    session.commit()

    return {"message": f"Unregistered {email} from {activity_name}"}
