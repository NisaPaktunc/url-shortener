"""Fill the database with demo data (a user, links and clicks).

Use it to try the dashboard or to take screenshots:

    python scripts/seed.py            # 45 days of data
    python scripts/seed.py --reset    # delete the old demo data first

Log in on /dashboard with demo@example.com / demo-password-123.

The data looks like real traffic: more clicks on weekdays, slow growth,
one spike day, mostly phones, and one link nobody has opened yet. The same
--seed always gives the same data.
"""

import argparse
import random
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Click, DeviceType, Link, User
from app.models.utils import utc_now
from app.services.user_service import register_user

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password-123"

DEFAULT_DAYS = 45
DEFAULT_RNG_SEED = 7
MIN_DAYS, MAX_DAYS = 7, 365


@dataclass(frozen=True)
class DemoLink:
    """One demo link and how popular it is."""

    code: str
    target_url: str
    created_at_fraction: float  # 0.98 = created about at the start of the window
    clicks_per_day: float  # average on a normal day, before the weekday pattern
    spike: bool = False  # one day with about 4 times more clicks


DEMO_LINKS = (
    DemoLink("launch", "https://example.com/blog/we-just-launched", 0.98, 4.5, True),
    DemoLink("docs", "https://example.com/docs/getting-started", 0.85, 3.0),
    DemoLink("newsletter", "https://example.com/newsletter/archive", 0.55, 3.0),
    DemoLink("portfolio", "https://example.com/portfolio/projects", 0.27, 2.0),
    DemoLink("quiet", "https://example.com/an/almost/unknown/page", 0.10, 0.0),
)

# Monday = 0 ... Sunday = 6. Fewer people click on weekends.
WEEKDAY_FACTOR = (1.2, 1.2, 1.2, 1.2, 1.2, 0.6, 0.5)

DEVICE_WEIGHTS = {
    DeviceType.MOBILE: 55,
    DeviceType.DESKTOP: 33,
    DeviceType.TABLET: 7,
    DeviceType.BOT: 5,
}

# None means a direct visit (no Referer header).
REFERRER_WEIGHTS = {
    None: 35,
    "https://www.google.com/": 25,
    "https://twitter.com/": 12,
    "https://www.linkedin.com/": 10,
    "https://news.ycombinator.com/": 8,
    "https://github.com/": 6,
    "https://www.reddit.com/": 4,
}


class DemoDataExistsError(Exception):
    """The demo data is already in the database. Use --reset to replace it."""


@dataclass(frozen=True)
class SeedResult:
    """How much data was created."""

    users: int
    links: int
    clicks: int


def _delete_demo_data(db: Session) -> None:
    """Remove the demo user with their links and clicks. Other users stay."""
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        return
    link_ids = select(Link.id).where(Link.owner_id == user.id)
    db.execute(delete(Click).where(Click.link_id.in_(link_ids)))
    db.execute(delete(Link).where(Link.owner_id == user.id))
    db.delete(user)
    db.commit()


def _check_nothing_in_the_way(db: Session) -> None:
    """Raise if the demo user or one of the demo codes is already used."""
    if db.scalar(select(User.id).where(User.email == DEMO_EMAIL)) is not None:
        raise DemoDataExistsError(
            f"The demo user {DEMO_EMAIL} already exists. "
            "Run again with --reset to replace the demo data."
        )
    codes = [link.code for link in DEMO_LINKS]
    taken = db.scalars(select(Link.code).where(Link.code.in_(codes))).all()
    if taken:
        raise DemoDataExistsError(
            f"These codes are used by another account: {', '.join(taken)}."
        )


def _clicks_for_day(rng: random.Random, expected: float) -> int:
    """Turn an average (like 3.4) into a whole number (3 or 4) at random."""
    whole = int(expected)
    return whole + (1 if rng.random() < expected - whole else 0)


def _pick_device(rng: random.Random) -> str:
    devices = list(DEVICE_WEIGHTS)
    return str(rng.choices(devices, weights=list(DEVICE_WEIGHTS.values()))[0])


def _pick_referrer(rng: random.Random, device: str) -> str | None:
    if device == DeviceType.BOT:
        return None  # crawlers do not send a Referer
    referrers = list(REFERRER_WEIGHTS)
    return rng.choices(referrers, weights=list(REFERRER_WEIGHTS.values()))[0]


def _make_clicks(
    rng: random.Random, link: Link, spec: DemoLink, start: datetime, now: datetime
) -> list[Click]:
    """Make the clicks of one link, day by day, from its creation until now."""
    if spec.clicks_per_day <= 0:
        return []
    total_days = max((now - start).days, 1)
    spike_day = int(total_days * 0.6)
    clicks: list[Click] = []
    day = link.created_at.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < now:
        # The click times of this day: not before the link exists, not in the future.
        first = max(day, link.created_at)
        last = min(day + timedelta(days=1), now)
        if last > first:
            index = (day - start).days
            trend = 1 + 0.5 * max(index, 0) / total_days  # slow growth
            expected = spec.clicks_per_day * WEEKDAY_FACTOR[day.weekday()] * trend
            if spec.spike and index == spike_day:
                expected *= 4
            expected *= (last - first) / timedelta(days=1)  # partial first/last day
            for _ in range(_clicks_for_day(rng, expected)):
                device = _pick_device(rng)
                clicks.append(
                    Click(
                        link_id=link.id,
                        clicked_at=first + (last - first) * rng.random(),
                        device_type=device,
                        referrer=_pick_referrer(rng, device),
                    )
                )
        day += timedelta(days=1)
    return clicks


def seed(
    db: Session,
    days: int = DEFAULT_DAYS,
    rng_seed: int = DEFAULT_RNG_SEED,
    now: datetime | None = None,
    reset: bool = False,
) -> SeedResult:
    """Create the demo user, links and clicks. Returns how many were made."""
    now = now or utc_now()
    if reset:
        _delete_demo_data(db)
    _check_nothing_in_the_way(db)

    rng = random.Random(rng_seed)
    start = now - timedelta(days=days)
    user = register_user(db, DEMO_EMAIL, DEMO_PASSWORD)

    clicks: list[Click] = []
    for spec in DEMO_LINKS:
        created_at = now - timedelta(days=days * spec.created_at_fraction)
        link = Link(
            code=spec.code,
            target_url=spec.target_url,
            owner_id=user.id,
            created_at=created_at,
        )
        db.add(link)
        db.flush()  # gives the link its id
        clicks.extend(_make_clicks(rng, link, spec, start, now))

    db.add_all(clicks)
    db.commit()
    return SeedResult(users=1, links=len(DEMO_LINKS), clicks=len(clicks))


def _days_argument(text: str) -> int:
    value = int(text)
    if not MIN_DAYS <= value <= MAX_DAYS:
        raise argparse.ArgumentTypeError(f"must be between {MIN_DAYS} and {MAX_DAYS}")
    return value


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill the database with demo data.")
    parser.add_argument("--days", type=_days_argument, default=DEFAULT_DAYS)
    parser.add_argument("--seed", type=int, default=DEFAULT_RNG_SEED)
    parser.add_argument(
        "--reset", action="store_true", help="delete the old demo data first"
    )
    parser.add_argument(
        "--force", action="store_true", help="allow a database that is not SQLite"
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run from the command line. Returns the exit code."""
    args = _parse_args(argv)
    url = make_url(settings.database_url)
    print(f"Database: {url.render_as_string(hide_password=True)}")

    if url.get_backend_name() != "sqlite" and not args.force:
        print(
            "Refusing to add demo data to a database that is not SQLite. "
            "Use --force if you really want this.",
            file=sys.stderr,
        )
        return 2

    with SessionLocal() as db:
        try:
            result = seed(db, args.days, args.seed, reset=args.reset)
        except DemoDataExistsError as error:
            print(error, file=sys.stderr)
            return 1
        except (OperationalError, ProgrammingError):
            print(
                "The tables are missing. Run `alembic upgrade head` first.",
                file=sys.stderr,
            )
            return 1

    print(
        f"Created {result.users} user, {result.links} links and "
        f"{result.clicks} clicks (last {args.days} days)."
    )
    print(f"Log in with {DEMO_EMAIL} / {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
