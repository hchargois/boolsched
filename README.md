# boolsched

A programmatic, composable scheduling system for Python using boolean logic.

You can think of it as an alternative to Cron syntax, but more expressive and
more powerful.

# A simple example

Let's say you want something to fire at noon every Monday.

This can be expressed in plain Python, using boolsched components and Python's
bitwise operators (`|`, `&`, `~`), like this:

```python
from boolsched import Monday, At

schedule = Monday & At("12")
```

You can think of it as "fire every time when it is both a Monday _and_ noon".

What if you also want it to run on Fridays, still at noon? Easy, you can just
add Friday in there: `(Monday | Friday) & At("12")`. This can be read as
"fire every time when it is either Monday _or_ Friday, _and_ noon".

A quick note, if you are not very familiar with boolean logic: beware of the
ambiguity of the word "and". In everyday language, you might say "I want this
to run on Mondays and Fridays". In logic speak, this is actually an "or", as you
want to run on days that are either a Monday or a Friday; an "and" would run on
days that are both a Monday and a Friday at the same time, which is impossible.

# Some more examples

```python
# Every day at 10:00, 14:30, and 18:37:45
schedule = At("10") | At("14:30") | At("18:37:45")

# At 10:00 and 18:00, but only on the weekend
schedule = (Saturday | Sunday) & (At("10:00") | At("18:00"))

# On the 15th and last day of each month at noon
schedule = (DayOfMonth(15) | DayOfMonth(-1)) & At("12")

# Every 15 minutes from 8:00 to 20:00 every day
schedule = Timerange("8:00", "20:00") & Every(minutes=15)

# Since you're dealing with plain Python objects and expressions, you can use
# variables for expressiveness
day = Timerange("8:00", "20:00")
night = ~day
schedule = (day & Every(minutes=10)) | (night & Every(minutes=30))

# Another example of a (slightly) complex schedule
weekend = Saturday | Sunday
weekend_schedule = weekend & At("14:00")
workdays_schedule = ~weekend & Timerange("8:00", "20:00") & Every(minutes=10)
schedule = weekend_schedule | workdays_schedule

# Another example: every 10 minutes but on different time ranges on weekdays and weekends
timeranges = (weekend & Timerange("10:00", "20:00")) | (workdays & Timerange("9:00", "17:00"))
schedule = timeranges & Every(minutes=10)
```

# Using schedules

By themselves, schedules are just a way to get the next datetime that matches
them, starting from a given point in time. This is done with the `next` method
of the schedule:

```python
schedule = At("14:30")

# Here we're using the ISO 8601 format encoding for the starting time, but you
# can also pass a datetime.datetime object
n = schedule.next("2024-01-01 12:00:00")

print(n) # 2024-01-01 14:30:00
```

Using that interface to actually _do_ things is up to you. Here's a simple
example of how you could run a function on a schedule forever, simply by
sleeping between calls:

```python
def run_on_schedule(schedule: boolsched.Schedule, func: Callable[[], None]):
    while True:
        now = datetime.datetime.now()
        must_sleep_for = schedule.next(now) - now
        time.sleep(must_sleep_for.total_seconds())
        func()
```

# Discrete vs continuous components

Despite the flexible way of expressing schedules by combining base components
(At, Monday, Timerange...) as shown above, there are actually two distinct types
of components:

- "discrete" components that match specific points in time (At, Every...)
- "continuous" components that match whole time ranges (Monday, Timerange...)

Combining these components with `&`, `|`, and `~` give new expresions that may
be either discrete or continuous, following rules that will be detailed below.

To call the `next` method on a schedule, it must be discrete. That should make
sense since `next` needs to return the next point in time that matches the
schedule, and continuous expressions match infinitely many points in time.

To illustrate, what would a schedule of just `Monday` mean? Would it fire just
once on Monday at midnight? Or every hour of Monday? Every minute? That
expression doesn't make sense on its own, or at least it is ambiguous, so it is
invalid to call `next` on it.

However, `Monday & At("12")` is a discrete expression that can be used as a
schedule and have its `next` method called. Visually, this could be represented
like that:

```
                    Sun   Mon   Tue   Wed   Thu   Fri   Sat   Sun   Mon   Tue  
                  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|> time
           Monday       <=====>                                   <=====>     
         At("12")    X     X     X     X     X     X     X     X     X     X  
Monday & At("12")          X                                         X        
```

`Monday` on its own is continuous and matches all times on every Monday, and
`At("12")` is discrete and matches exactly 12:00 every day. By combining both
with `&`, we get a (discrete) schedule that fires every Monday at 12:00.

The full rules for combining discrete and continuous components are as follows:

- continuous & continuous -> continuous
- continuous & discrete -> discrete
- continuous | continuous -> continuous
- discrete | discrete -> discrete
- ~continuous -> continuous

These combinations are invalid:

- discrete & discrete -> invalid
- continuous | discrete -> invalid
- ~discrete -> invalid

The reason why they're invalid is left as an exercise for the reader.

Usually, you shouldn't have to think about all these rules. If the schedule
makes sense, it should be valid.

# Components

## Continuous

### Weekday

`Weekday(n)` matches the n-th day of the week, from Monday=1 to Sunday=7.

For convenience, predeclared instances of this component are available, so you
can simply use `Monday` to `Sunday`.

### DayOfMonth

`DayOfMonth(n)` matches the n-th day of the month, from 1 to 31.

There is no adjustment made for months with less than 31 days, so
`DayOfMonth(31)` will simply not match any day in months with less than 31 days.

If n is negative, it matches the n-th day of the month starting from the end of
the month. For example, `DayOfMonth(-1)` will match the last day of the month.

A variation of this, using two parameters, `DayOfMonth(from, to)`, will match
days between `from` and `to` (both inclusive).

For example, `DayOfMonth(1, 7) & Monday` expresses a schedule that matches the
first Monday of every month.

### Timerange

`Timerange(start, end)` matches times between `start` (inclusive) and `end`
(exclusive).

For example, `Timerange("10:00", "20:00")` will match times between 10:00 and
20:00, including 10:00:00 but excluding 20:00:00 (so the last time that matches
is 19:59:59).

A Timerange where `start` is greater than `end` is valid, and goes through
midnight. For example, `Timerange("20:00", "10:00")` will match times between
20:00 on one day up to 10:00 on the next day.

`start` and `end` can be passed as strings in `HH`, `HH:MM`, or `HH:MM:SS`
format; or they can be passed as `datetime.time` objects.

## Discrete

### At

`At(time)` matches exactly `time`.

For example, `At("12:00")` will match exactly 12:00:00 every day.

`time` can be passed as a string in `HH`, `HH:MM`, or `HH:MM:SS` format; or it
can be passed as a `datetime.time` object.

### Every

`Every(seconds, minutes, hours)` matches times separated by the specified
interval.

For example, `Every(hours=1, minutes=2, seconds=3)` will match times that are
each 1 hour + 2 minutes + 3 seconds = 3723 seconds apart.

You should not assume anything about the specific times matched, except that
they're separated by that interval. In particular you should not assume that
any pattern of divisility exists, for example `Every(minutes=7)` does _not_ mean
that the schedule will fire on the 0th, 7th, 14th... minute of each hour.

See the "Why not Cron?" section for more details about why that's a good thing.

## Operators

Throughout this documentation, we've used the bitwise operators `|`, `&`, and
`~` for combining components. They're actually just syntactic sugar for the
operators `Or`, `And`, and `Not`, respectively.

For example, `At("10") | At("12") | At("14")` is equivalent to
`Or(At("10"), At("12"), At("14"))`

You can use these classes instead of the bitwise operators if you prefer or if
it's more practical, for example if you are generating schedules
programmatically:

```python
# at 11:11, 12:12, 13:13, ..., 19:19
times = [At(f"{x}:{x}") for x in range(11, 20)]
schedule = Or(*times)
```

# Limitations

## Performance

boolsched is currently implemented in a very simple way. Calling `next` on a
schedule checks incrementing datetimes in a loop until it finds one that 
satisfies the schedule. This is not super efficient, but it's still reasonably
fast. It's also usually not a problem since you will probably be waiting until
that next point in time anyway.

There is some optimization done when not using seconds in the discrete
components, so if you can, you should use whole minutes in `At` or `Every`.

## Compatibility

boolsched internally uses timestamps from Python's standard library's "time"
package. In particular it relies on leap seconds not being counted in the
timestamps, i.e. that all days have exactly 86400 seconds.

Python's documentation indicates that this is platform dependent; however, it
also says that "Windows and most Unix systems" behave as we want, which should
cover most of everything out there.

# Why not Cron?

You may ask, why not just use Cron (syntax)?

There are multiple reasons.

## Expressiveness

Cron syntax is not very expressive. I, for one, never remember which element of
the Cron line represents the day of month, day of week, hour or minute. It
doesn't help that there are actually multiple Cron syntax implementations with
different meanings and extensions.

Judging from the multitude of websites that exist purely to help with creating
or explaining a Cron line (Google for "Cron helper"), I'd say that's a common
issue.

For example, compare:

```
*/5 10-14 * * 1
```

and:

```python
Monday & Timerange("10:00", "15:00") & Every(minutes=5)
```

Which is the most evident to you?

## Composability

With Cron you are quite limited with what you can do in a single schedule. For
example, you can't express things as simple as "at 10:00 and at 15:30" in a
single schedule.

In boolsched you can compose any arbitrarily complex schedule trivially by
adding up multiple simpler schedules with the `|` operator.

## Intervals and the "every" lie

Let me ask you a question. How would you express "every 5 minutes between 10:00
and 14:59" in Cron? Easy! As we've done above, it's:

```
*/5 10-14 * * *
```

Now, how about "every _7_ minutes between 10:00 and 14:59"? Same thing, right?

```
*/7 10-14 * * *
```

Well, yes... But actually no. You see, in Cron, `*/n` _doesn't_ really mean
"every _n_ minutes" (or hour or whatever depending on where it's placed). Even
if nearly all of the "Cron helpers" on the web would tell you it does.

It actually means "when the value of the minute (or hour...) is a multiple of
_n_". So that last schedule is in fact equivalent to:

```
0,7,14,21,28,35,42,49,56 10-14 * * *
```

And that means it will trigger at 10:56 and then at 11:00. Which are only _4_
minutes apart.

Maybe in that case that's not a big deal, one interval is 3 minutes short, who
cares, right? But think about other intervals, what if you wanted to trigger
every 45 minutes? `*/45` would trigger at 10:00, 10:45, 11:00, 11:45, 12:00...
Now you get very imbalanced intervals, probably not what you want.

Intervals in Cron are only exact if _n_ divides 60, which is the case for 5 but
not for 7.

In boolsched, `Every(minutes=n)` really means every _n_ minutes.

Cron is also limited to intervals of a single "scale". You can have intervals
of minutes, or of hours, but not both. For example. you cannot express
"every hour and a half" in a single Cron schedule. In boolsched, it's simply
`Every(hours=1, minutes=30)`.

## Ranges

While it's true that Cron has ways of expressing ranges of values, in many cases
it's not enough to express what you want in a single schedule.

For example, how would you express a schedule that must run every 5 minutes
between 10:22 and 15:33? With Cron, you cannot do that in a single line, you
have to use multiple schedules, and that's what they would look like:

```
22-59/5    10 * * *
    */5 11-14 * * *
 0-33/5    15 * * *
```

Quite awful. Again, compare that to the same schedule in boolsched:

```python
Timerange("10:22", "15:33") & Every(minutes=5)
```
