from collections import defaultdict
from datetime import timedelta, datetime, timezone
import re
import time
from .parser import max_kleene, cat, alt, token, drop_token, natural, maybe, eos, map, EOS
from .sentinel import Sentinel

RE = re.compile(r'((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')


def parse(time):
    return timedelta(**{k: int(v) if v is not None else 0 for k, v in RE.fullmatch(time).groupdict().items()})


class Schedule:
    def __init__(self, text):
        self.text = text
        self.weekday_to_period = _parse(text)    # {0-6: ((h, m), (h, m))

    NOW = Sentinel("NOW")

    def next_time_in_period(self, t=NOW, delta=0):
        """Compute a period in the future

        From the start time, t, count forward delta seconds, only counting those seconds in the active periods.
        """
        if t is Schedule.NOW:
            t = time.time()
        if not isinstance(delta, timedelta):
            delta = timedelta(seconds=delta)
        gmt = datetime.fromtimestamp(t, timezone.utc)
        while True:
            daily_schedule = self.weekday_to_period[gmt.weekday()]
            for start, end in sorted(daily_schedule):
                start = gmt.replace(hour=start[0], minute=start[1], second=0, microsecond=0)
                end = gmt.replace(hour=end[0], minute=end[1], second=0, microsecond=0)
                if end <= gmt:
                    pass
                elif gmt < start:
                    gmt = start
                if start <= gmt < end:
                    if gmt + delta < end:
                        return (gmt + delta).timestamp()
                    delta -= end - gmt
                    gmt = end
            else:
                # No period during this day, try the next one
                gmt = gmt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                continue


class EmptySchedule:
    NOW = Sentinel("NOW")

    def next_time_in_period(self, t=NOW, delta=0):
        if t is EmptySchedule.NOW:
            t = time.time()
        if not isinstance(delta, timedelta):
            delta = timedelta(seconds=delta)
        gmt = datetime.fromtimestamp(t) + delta
        return gmt.timestamp()


def _parse(text):
    """Parse sequences of:

    dayspec timespec ...
    dayspec : day | day [ , dayspec ]* | day-day [ , dayspec ]*
    timespec : [ start-end [, start-end ]* ]?
    start : time
    end : time
    time : hour [ : minute ]?
    """
    weekday_to_period = defaultdict(list)    # {0-6: ((h, m), (h, m))
    for (items, end), text in cat(max_kleene(cat(day_spec, time_specs)), eos)(text):
        assert text == "" and end is EOS

        for ds, ts in items:
            if ts == []:
                ts = [((0, 0), (23, 59))]

            def bump_end(start, end):
                if end[0] < start[0] <= 12:
                    end = (end[0] + 12, end[1])
                return start, end

            ts = [bump_end(start, end) for (start, end) in ts]
            for d in ds:
                weekday_to_period[DAYS.index(d)].extend(ts)

        break

    return weekday_to_period


DAYS = 'mon tue wed thu fri sat sun'.split()
day = alt(*(token(x) for x in DAYS))


def day_succ(d):
    return DAYS[(DAYS.index(d) + 1) % len(DAYS)]


def days_between(d1, d2):
    result = [d2]
    while d1 != d2:
        result.append(d1)
        d1 = day_succ(d1)
    return frozenset(result)


day_to_day = map(cat(day, maybe(cat(drop_token("-"), day))),
                 lambda d2d: frozenset([d2d[0]]) if d2d[1] is None else days_between(d2d[0], d2d[1][0]))

day_spec = map(cat(day_to_day,
                   map(max_kleene(cat(drop_token(","), day_to_day)),
                       lambda xs: frozenset().union(*xs))),
               lambda xs: xs[0].union(xs[1]))

time_part = map(cat(natural, maybe(cat(token(":"), natural))),
                lambda ts: (ts[0], 0) if ts[1] is None else (ts[0], ts[1][1]))

time_spec = map(cat(time_part, token("-"), time_part),
                lambda ts: (ts[0], ts[2]))

time_specs = max_kleene(time_spec)
time_specs = map(cat(time_spec,
                     max_kleene(cat(drop_token(","), time_spec))),
                 lambda xs: [xs[0]] + [x[0] for x in xs[1]])
