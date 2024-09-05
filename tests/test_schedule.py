import datetime

from pytest import raises

from boolsched import (
    Every,
    DayOfMonth,
    At,
    Monday,
    Tuesday,
    Wednesday,
    Thursday,
    Friday,
    Saturday,
    Sunday,
    Timerange,
    Or,
    And,
)
from boolsched.schedule import _parse_time


def test_every():
    sched = Every(seconds=3)
    dt = datetime.datetime(2020, 1, 1, 0, 0, 0)
    ts = int(dt.timestamp())
    assert sched.satisfies(dt, ts)
    assert not sched.satisfies(dt + datetime.timedelta(seconds=1), ts + 1)
    assert not sched.satisfies(dt + datetime.timedelta(seconds=2), ts + 2)
    assert sched.satisfies(dt + datetime.timedelta(seconds=3), ts + 3)

    weekend = Saturday | Sunday
    weekdays = ~weekend
    sched = weekdays & Every(seconds=3)

    next = sched.next(dt)
    assert next == dt + datetime.timedelta(seconds=3)
    next = sched.next(next)
    assert next == dt + datetime.timedelta(seconds=6)
    next = sched.next(next)
    assert next == dt + datetime.timedelta(seconds=9)

    next_3 = sched.next_n(dt, 3)
    assert next_3 == [
        dt + datetime.timedelta(seconds=3),
        dt + datetime.timedelta(seconds=6),
        dt + datetime.timedelta(seconds=9),
    ]


def test_at():
    for sched in [
        # two ways of writing the same schedule
        At("14:15:16"),
        At(datetime.time(14, 15, 16)),
        # microseconds should be discarded
        At(datetime.time(14, 15, 16, 17)),
    ]:
        dt = datetime.datetime(2020, 1, 1, 0, 0, 0)
        assert not sched.satisfies(dt, int(dt.timestamp()))

        dt = datetime.datetime(2020, 1, 1, 14, 15, 16)
        assert sched.satisfies(dt, int(dt.timestamp()))


def test_or():
    sched = Monday | (Tuesday | Wednesday | Thursday) | Friday
    assert isinstance(sched, Or)
    assert len(sched.operands) == 5

    with raises(TypeError):
        _ = Monday | 42


def test_and():
    sched = Monday & (Tuesday & Wednesday & Thursday) & Friday
    assert isinstance(sched, And)
    assert len(sched.operands) == 5

    with raises(TypeError):
        _ = Monday & 42


def test_boolean_operators():
    with raises(TypeError):
        _ = Monday or Tuesday
    with raises(TypeError):
        _ = Monday and Tuesday
    with raises(TypeError):
        _ = not Monday


def test_stop():
    sched = Monday & Tuesday & Every(hours=1)  # impossible schedule
    with raises(StopIteration):
        _ = sched.next(datetime.datetime(2020, 1, 1, 0, 0, 0))


def test_invalid_schedules():
    dt = datetime.datetime(2020, 1, 1, 0, 0, 0)
    with raises(ValueError):
        sched = Monday
        _ = sched.next(dt)

    with raises(ValueError):
        sched = Every(minutes=1) & Every(minutes=2)
        _ = sched.next(dt)

    with raises(ValueError):
        sched = Monday | Every(minutes=1)
        _ = sched.next(dt)

    with raises(ValueError):
        sched = ~Every(minutes=1)


def test_timerange():
    sched = Timerange("10:00", "11:00")

    dt = datetime.datetime(2020, 1, 1, 9, 59, 0)
    assert not sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 1, 10, 0, 0)
    assert sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 1, 10, 1, 0)
    assert sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 1, 11, 0, 0)
    assert not sched.satisfies(dt, int(dt.timestamp()))

    sched = Timerange("11:00", "10:00")

    dt = datetime.datetime(2020, 1, 1, 9, 59, 0)
    assert sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 1, 10, 0, 0)
    assert not sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 1, 10, 1, 0)
    assert not sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 1, 11, 0, 0)
    assert sched.satisfies(dt, int(dt.timestamp()))

    sched = Timerange("10:00", "00:00")
    dt = datetime.datetime(2020, 1, 1, 11, 0, 0)
    assert sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 1, 0, 0, 0)
    assert not sched.satisfies(dt, int(dt.timestamp()))

    sched = Timerange("00:00", "10:00")
    dt = datetime.datetime(2020, 1, 1, 11, 0, 0)
    assert not sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 1, 0, 0, 0)
    assert sched.satisfies(dt, int(dt.timestamp()))


def test_parse_time():
    assert _parse_time("10") == datetime.time(10)
    assert _parse_time("10:20") == datetime.time(10, 20)
    assert _parse_time("10:20:30") == datetime.time(10, 20, 30)

    assert _parse_time("08:09") == datetime.time(8, 9)
    # leading 0s can be omitted
    assert _parse_time("8:9") == datetime.time(8, 9)
    # whitespace can be added
    assert _parse_time(" 8 : 9 ") == datetime.time(8, 9)

    with raises(ValueError):
        _ = _parse_time("hello")
    with raises(ValueError):
        _ = _parse_time("10:20:30:40")
    with raises(ValueError):
        _ = _parse_time("24:20:30")
    with raises(ValueError):
        _ = _parse_time("10:60:30")
    with raises(ValueError):
        _ = _parse_time("10:20:60")
    with raises(ValueError):
        _ = _parse_time("-10")


def test_day_of_month():
    with raises(ValueError):
        _ = DayOfMonth(0)

    with raises(ValueError):
        _ = DayOfMonth(32)

    with raises(ValueError):
        _ = DayOfMonth(-32)

    sched = DayOfMonth(1)
    dt = datetime.datetime(2020, 1, 1, 0, 0, 0)
    assert sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 2, 0, 0, 0)
    assert not sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 3, 0, 0, 0)
    assert not sched.satisfies(dt, int(dt.timestamp()))

    sched = DayOfMonth(-1)
    dt = datetime.datetime(2020, 1, 30, 0, 0, 0)
    assert not sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 1, 31, 0, 0, 0)
    assert sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2020, 2, 29, 0, 0, 0)
    assert sched.satisfies(dt, int(dt.timestamp()))

    dt = datetime.datetime(2021, 2, 28, 0, 0, 0)
    assert sched.satisfies(dt, int(dt.timestamp()))


def test_day_of_month_range():
    with raises(ValueError):
        _ = DayOfMonth(1, 0)

    with raises(ValueError):
        _ = DayOfMonth(1, 32)

    with raises(ValueError):
        _ = DayOfMonth(1, -32)

    for sched in [
        # order does not matter
        DayOfMonth(10, 20),
        DayOfMonth(20, 10),
    ]:
        for day in range(1, 31):
            dt = datetime.datetime(2020, 1, day, 0, 0, 0)
            exp_satisfy = day >= 10 and day <= 20
            assert sched.satisfies(dt, int(dt.timestamp())) == exp_satisfy

    for sched in [
        # order does not matter
        DayOfMonth(-10, -20),
        DayOfMonth(-20, -10),
    ]:
        for day in range(1, 31):
            dt = datetime.datetime(2020, 1, day, 0, 0, 0)
            exp_satisfy = day >= 12 and day <= 22
            assert sched.satisfies(dt, int(dt.timestamp())) == exp_satisfy
