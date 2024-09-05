import datetime
from abc import ABC, abstractmethod
from math import gcd

Timestamp = int


class Schedule(ABC):
    """Base class for all schedules."""

    def __bool__(self) -> bool:
        # this protects against mistakenly using "or" and "and" (instead
        # of bitwise operators | and &)
        # e.g.
        #    Monday or Tuesday # Wrong! Will raise TypeError
        #    Monday | Tuesday # Correct
        raise TypeError(
            "use bitwise operators (| & ~), not boolean operators (or not and)"
        )

    def __or__(self, other) -> "Or":
        if not isinstance(other, Schedule):
            return NotImplemented

        # If either side is already an Or, we flatten the operands to avoid
        # nesting Or's
        if isinstance(self, Or):
            left = self.operands
        else:
            left = (self,)

        if isinstance(other, Or):
            right = other.operands
        else:
            right = (other,)

        return Or(*left, *right)

    def __and__(self, other) -> "And":
        if not isinstance(other, Schedule):
            return NotImplemented

        if isinstance(self, And):
            left = self.operands
        else:
            left = (self,)

        if isinstance(other, And):
            right = other.operands
        else:
            right = (other,)

        return And(*left, *right)

    def __invert__(self) -> "Schedule":
        if self.step() is not None:
            raise ValueError("cannot invert a discrete operator")
        if isinstance(self, Not):
            # Not of Not can be simplified
            return self.operand
        return Not(self)

    @abstractmethod
    def satisfies(self, dt: datetime.datetime, ts: Timestamp) -> bool:
        raise NotImplementedError

    @abstractmethod
    def step(self) -> int | None:
        raise NotImplementedError

    def next(
        self, dt: datetime.datetime | str, stop_at: datetime.datetime | None = None
    ) -> datetime.datetime:
        """Returns the next time (a time strictly after dt) that satisfies the
        schedule.
        If no such time is found before stop_at (which defaults to one year
        after dt), StopIteration is raised.
        """
        step = self.step()
        if step is None:
            raise ValueError("schedule is not discrete")

        if isinstance(dt, str):
            dt = datetime.datetime.fromisoformat(dt)

        if stop_at is None:
            stop_at = dt + datetime.timedelta(days=366)

        ts = int(dt.timestamp())
        ts = (ts // step) * step  # align the ts on a whole step

        tz = dt.tzinfo

        while dt < stop_at:
            ts += step
            dt = datetime.datetime.fromtimestamp(ts, tz=tz)
            if self.satisfies(dt, ts):
                return dt

        raise StopIteration

    def next_n(
        self,
        dt: datetime.datetime | str,
        n: int,
        stop_at: datetime.datetime | None = None,
    ) -> list[datetime.datetime]:
        """Returns a list of the n next times that satisfy the schedule"""
        if isinstance(dt, str):
            dt = datetime.datetime.fromisoformat(dt)

        if stop_at is None:
            stop_at = dt + datetime.timedelta(days=366)

        nexts = []
        try:
            for _ in range(n):
                dt = self.next(dt, stop_at)
                nexts.append(dt)
        except StopIteration:
            pass
        return nexts


class Continuous(Schedule):
    def step(self) -> int | None:
        return None


class Discrete(Schedule):
    pass


class Not(Continuous):
    def __init__(self, operand: Schedule):
        self.operand = operand

    def satisfies(self, dt: datetime.datetime, ts: Timestamp) -> bool:
        return not self.operand.satisfies(dt, ts)


class Or(Schedule):
    def __init__(self, *operands: Schedule):
        self.operands = operands

    def satisfies(self, dt: datetime.datetime, ts: Timestamp) -> bool:
        return any(arg.satisfies(dt, ts) for arg in self.operands)

    def step(self) -> int | None:
        steps: list[int] = []
        for op in self.operands:
            step = op.step()
            if step is not None:
                steps.append(step)

        if len(steps) == 0:
            return None

        if len(steps) == len(self.operands):
            return gcd(*steps)

        raise ValueError("cannot combine discrete and continuous operators with |")


class And(Schedule):
    def __init__(self, *operands: Schedule):
        self.operands = operands

    def satisfies(self, dt: datetime.datetime, ts: Timestamp) -> bool:
        return all(arg.satisfies(dt, ts) for arg in self.operands)

    def step(self) -> int | None:
        steps: list[int] = []
        for op in self.operands:
            step = op.step()
            if step is not None:
                steps.append(step)

        if len(steps) == 0:
            return None

        if len(steps) > 1:
            raise ValueError("cannot combine discrete operators with &")

        return steps[0]


class Weekday(Continuous):
    """A continuous schedule that matches a specific day of the week, from
    1 (Monday) to 7 (Sunday).
    """

    def __init__(self, weekday: int):
        if not 1 <= weekday <= 7:
            raise ValueError(f"weekday must be 1-7, not {weekday}")
        self.weekday = weekday

    def satisfies(self, dt: datetime.datetime, ts: Timestamp) -> bool:
        return dt.isoweekday() == self.weekday


class Every(Discrete):
    """A discrete schedule that matches times separated by the specified
    interval.
    """

    def __init__(self, seconds=0, minutes=0, hours=0):
        self.delta = hours * 3600 + minutes * 60 + seconds

    def satisfies(self, dt: datetime.datetime, ts: Timestamp) -> bool:
        return ts % self.delta == 0

    def step(self) -> int | None:
        return self.delta


class At(Discrete):
    """A discrete schedule that matches at the specified time of day every day."""

    def __init__(self, time: str | datetime.time):
        self.time = _parse_time(time)

    def satisfies(self, dt: datetime.datetime, ts: Timestamp) -> bool:
        return dt.time() == self.time

    def step(self) -> int | None:
        if self.time.second != 0:
            return gcd(self.time.second, 60)
        # maximum step is 15 minutes, because standard times may be offset by
        # multiples of 15 minutes relative to UTC
        return gcd(self.time.minute, 15) * 60


class Timerange(Continuous):
    """A continuous schedule that matches all times within the specified range.
    The order of the start and end times matters.
    """

    def __init__(self, start: str | datetime.time, end: str | datetime.time):
        self.start = _parse_time(start)
        self.end = _parse_time(end)
        if self.start == self.end:
            raise ValueError("start and end must be different")
        # forward interval is an interval such as 10:00 - 20:00, as opposed to
        # a backward interval such as 20:00 - 10:00, i.e. from 20 to 10 the next
        # day, through midnight
        self._forward = self.start < self.end

    def satisfies(self, dt: datetime.datetime, ts: Timestamp) -> bool:
        time = dt.time()
        if self._forward:
            return self.start <= time < self.end
        return self.start <= time or time < self.end


class DayOfMonth(Continuous):
    """A continuous schedule that matches the specified day of the month. If a
    second day is specified, the full range of days between the two (including
    them) is matched. If negative, it is counted from the end of the month.
    """

    def __init__(self, day: int, day2: int | None = None):
        if not 1 <= day <= 31 and not -31 <= day <= -1:
            raise ValueError(
                f"day must be between 1 and 31 (or between -31 and -1), not {day}"
            )
        if day2 is not None and not 1 <= day2 <= 31 and not -31 <= day2 <= -1:
            raise ValueError(
                f"day must be between 1 and 31 (or between -31 and -1), not {day2}"
            )
        self.day = day
        self.day2 = day2

    def satisfies(self, dt: datetime.datetime, ts: Timestamp) -> bool:
        day = self.day
        if day < 0:
            day = _days_in_month(dt.year, dt.month) + day + 1

        if self.day2 is None:
            return dt.day == day

        day2 = self.day2
        if day2 < 0:
            day2 = _days_in_month(dt.year, dt.month) + day2 + 1

        if day2 < day:
            day, day2 = day2, day
        return day <= dt.day <= day2


def _parse_time(time: str | datetime.time) -> datetime.time:
    if isinstance(time, datetime.time):
        return time.replace(microsecond=0)

    # datetime.time.fromisoformat() doesn't support times missing the leading 0
    # e.g. "2:00", it must be written "02:00". That's a bit annoying, so we'll
    # implement a custom parser

    elts = time.split(":")
    if len(elts) > 3:
        raise ValueError(f"invalid time: {time}")

    hour, minute, second = int(elts[0]), 0, 0
    if len(elts) >= 2:
        minute = int(elts[1])
    if len(elts) == 3:
        second = int(elts[2])

    return datetime.time(hour, minute, second)


def _days_in_month(year: int, month: int) -> int:
    # calendar.monthrange does that but also gives the weekday of the first
    # day of the month, which we don't care about; so for performance
    # reasons, we'll just copy-paste and inline the relevant code

    mdays = (0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if month == 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        return 29
    return mdays[month]


Monday = Weekday(1)
Tuesday = Weekday(2)
Wednesday = Weekday(3)
Thursday = Weekday(4)
Friday = Weekday(5)
Saturday = Weekday(6)
Sunday = Weekday(7)
