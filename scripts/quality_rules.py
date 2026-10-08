"""The data quality rules the dashboard checks the TLC trip records against.

One place for what each rule is, which dimension it belongs to, what it tests, how the
result should be read, and the SQL that tests it. scripts/fetch_tlc.py runs the row rules
over each month's trip file while the file is on disk; src/data/quality.zip.py runs the
month rules over the committed facts at build time and ships this registry to the page as
rules.json, so the Data Quality tab and the pipeline can never disagree about a rule.

Dimensions follow DAMA UK's six (completeness, uniqueness, timeliness, validity, accuracy,
consistency) plus two more of DAMA-DMBOK's nine: integrity (the record's references hold)
and reasonability (the patterns look like what this data usually does).

Every rule carries a verdict, which is our reading rather than a measurement:
  defect             the record is wrong, or something is missing that should be there
  business rule      the record is right and the rule was naive; a rule written from the
                     documentation alone would raise a false alarm here
  documentation gap  the record may well be right, but nothing TLC publishes lets a
                     consumer tell; the fix is a sentence in the data dictionary
"""

from dataclasses import dataclass

# Alphabetical. The order here is the order
# the scorecard and the rule list use, so a reader looking for a dimension finds it where
# they expect rather than where the rules happened to be written.
DIMENSIONS = {
    "accuracy": "Does the record match an authoritative source?",
    "completeness": "Is every value that should be present, present?",
    "consistency": "Do values agree with each other, within a record and across records?",
    "integrity": "Do the relationships between records and files hold?",
    "reasonability": "Do the patterns look like what this data usually does?",
    "timeliness": "Is the data current enough, and here when a consumer needs it?",
    "uniqueness": "Is each trip recorded once?",
    "validity": "Does each value conform to its defined domain, format and type?",
}

VERDICTS = ("defect", "business rule", "documentation gap")
SEVERITIES = ("error", "warning")

# Trips that begin or end at an airport are charged the airport fee; these are TLC's zone
# ids for Newark, JFK and LaGuardia. 264 is "Unknown" and 265 is "Outside of NYC" in TLC's
# own lookup table.
AIRPORT_ZONES = "(1, 132, 138)"

# The fields the data dictionary describes, every one of which a trip should carry.
REQUIRED = [
    "hvfhs_license_num", "dispatching_base_num", "request_datetime", "pickup_datetime",
    "dropoff_datetime", "PULocationID", "DOLocationID", "trip_miles", "trip_time",
    "base_passenger_fare", "tolls", "bcf", "sales_tax", "congestion_surcharge", "airport_fee",
    "tips", "driver_pay", "shared_request_flag", "shared_match_flag", "access_a_ride_flag",
    "wav_request_flag", "wav_match_flag", "cbd_congestion_fee",
]
FLAGS = ["shared_request_flag", "shared_match_flag", "access_a_ride_flag", "wav_request_flag", "wav_match_flag"]
MONEY = ["tolls", "bcf", "sales_tax", "congestion_surcharge", "airport_fee", "cbd_congestion_fee", "tips"]

# The columns the trip view adds to TLC's own, so a rule can be written against them:
#   company     Uber or Lyft, from hvfhs_license_num
#   day         the pickup date
#   elapsed     dropoff minus pickup in seconds, reading the timestamps as written
#   elapsed_ny  the same, reading them as New York local time, so a trip across the
#               spring clock change measures its true length
#   fall_back   the pickup falls in the early hours of the night the clocks go back, when
#               the same wall-clock hour happens twice and a timestamp cannot say which
TRIPS_VIEW = """
    SELECT t.*,
        CASE t.hvfhs_license_num WHEN 'HV0003' THEN 'Uber' WHEN 'HV0005' THEN 'Lyft' END AS company,
        CAST(t.pickup_datetime AS DATE) AS day,
        date_diff('second', t.pickup_datetime, t.dropoff_datetime) AS elapsed,
        date_diff('second', timezone('America/New_York', t.pickup_datetime),
                            timezone('America/New_York', t.dropoff_datetime)) AS elapsed_ny,
        (month(t.pickup_datetime) = 11 AND isodow(t.pickup_datetime) = 7
            AND day(t.pickup_datetime) <= 7 AND hour(t.pickup_datetime) < 3) AS fall_back
    FROM read_parquet('{trips_path}', union_by_name = true) t
    WHERE t.hvfhs_license_num IN ('HV0003', 'HV0005')
"""

# The file has no trip identifier, so this combination of fields stands in for a key.
TRIP_KEY = ["company", "request_datetime", "pickup_datetime", "dropoff_datetime", "PULocationID", "DOLocationID", "trip_miles"]

# Tables built over the trips view before the rules run, in order. Twenty million rows
# grouped by seven columns is gigabytes of hash table; grouped by one hash of them it is a
# few hundred megabytes, and only the handful of colliding rows need the exact comparison.
PREPARE = {
    "dupe_hashes": f"SELECT hash({', '.join(TRIP_KEY)}) AS h FROM trips GROUP BY h HAVING count(*) > 1",
    "key_dupes": f"""SELECT {', '.join(TRIP_KEY)}, day, count(*) AS n FROM trips
                     WHERE hash({', '.join(TRIP_KEY)}) IN (SELECT h FROM dupe_hashes)
                     GROUP BY ALL HAVING count(*) > 1""",
}

# The schema the March 2025 data dictionary describes, in the files' own column order and
# DuckDB's names for the parquet types. VAL-10 compares each month against it.
EXPECTED_SCHEMA = [
    ["hvfhs_license_num", "VARCHAR"], ["dispatching_base_num", "VARCHAR"], ["originating_base_num", "VARCHAR"],
    ["request_datetime", "TIMESTAMP"], ["on_scene_datetime", "TIMESTAMP"], ["pickup_datetime", "TIMESTAMP"],
    ["dropoff_datetime", "TIMESTAMP"], ["PULocationID", "INTEGER"], ["DOLocationID", "INTEGER"],
    ["trip_miles", "DOUBLE"], ["trip_time", "BIGINT"], ["base_passenger_fare", "DOUBLE"], ["tolls", "DOUBLE"],
    ["bcf", "DOUBLE"], ["sales_tax", "DOUBLE"], ["congestion_surcharge", "DOUBLE"], ["airport_fee", "DOUBLE"],
    ["tips", "DOUBLE"], ["driver_pay", "DOUBLE"], ["shared_request_flag", "VARCHAR"], ["shared_match_flag", "VARCHAR"],
    ["access_a_ride_flag", "VARCHAR"], ["wav_request_flag", "VARCHAR"], ["wav_match_flag", "VARCHAR"],
    ["cbd_congestion_fee", "DOUBLE"],
]

# The licence codes the dictionary lists, and the two that still dispatch trips.
DOCUMENTED_LICENSES = {"HV0002": "Juno", "HV0003": "Uber", "HV0004": "Via", "HV0005": "Lyft"}

# TML-01: TLC's data page says about two months after the month; this is the line.
PUBLICATION_LAG_DAYS = 62
# ACC-02: two TLC publications of one month should agree to well within this.
RECONCILE_TOLERANCE = 0.005
# RSN-01: a day this far under its expected volume is either an event or a short file.
VOLUME_DROP = 0.25

# Days the volume rule flags that have a known cause. Holidays are business as usual; the
# two storms are named in the entries below.
KNOWN_VOLUME_CAUSES = {
    "2025-11-27": "Thanksgiving", "2025-11-28": "Thanksgiving weekend", "2025-11-29": "Thanksgiving weekend",
    "2025-12-24": "Christmas Eve", "2025-12-25": "Christmas Day", "2025-12-26": "Christmas holiday",
    "2025-12-27": "Christmas holiday", "2025-12-28": "Christmas holiday",
    "2026-01-01": "New Year's Day", "2026-01-02": "New Year holiday", "2026-01-03": "New Year holiday", "2026-01-04": "New Year holiday",
    "2026-01-25": "Blizzard: 11 to 15 inches of snow across the five boroughs",
    "2026-01-26": "Day after the 25 January blizzard",
    "2026-02-23": "Blizzard: city travel ban on all streets until noon",
}


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    dimension: str
    severity: str
    verdict: str
    test: str  # what the rule checks, in a sentence
    why: str  # what goes wrong for a consumer of the data when it fails
    note: str  # how to read the result: what the numbers turned out to mean
    sql: str = ""  # a predicate over the trips view, TRUE for a failing trip
    applies: str = "TRUE"  # the trips the rule is checked against (the denominator)
    group_sql: str = ""  # instead of a predicate: a query returning company, day, failed
    columns: tuple = ()  # the columns an example record shows
    month: bool = False  # a rule over a month's facts, evaluated at build time

    @property
    def grain(self):
        return "month" if self.month else "trip"


RULES = [
    # Completeness
    Rule("CMP-01", "Originating base missing", "completeness", "warning", "defect",
         "originating_base_num is null.",
         "The field is meant to say which base took the request. Without it a consumer cannot separate trips a company dispatched itself from trips it took on from another base, and a join to the base licence list drops the row.",
         "Uber fills it on every trip. Lyft fills it only when the passenger asked for a wheelchair-accessible vehicle and leaves it null on every other trip, so the gap is one company's reporting practice, not random loss.",
         sql="originating_base_num IS NULL",
         columns=("company", "dispatching_base_num", "originating_base_num", "wav_request_flag", "pickup_datetime")),
    Rule("CMP-02", "On-scene time missing", "completeness", "warning", "documentation gap",
         "on_scene_datetime is null.",
         "The dictionary says this field applies to accessible vehicles only, so a consumer following it would expect nulls on most trips and plan around them.",
         "There are no nulls. Both companies report an on-scene time on every trip, so the data is more complete than its documentation says. The rule passes and the dictionary is what needs the fix.",
         sql="on_scene_datetime IS NULL",
         columns=("company", "request_datetime", "on_scene_datetime", "pickup_datetime", "wav_request_flag")),
    Rule("CMP-03", "Required field missing", "completeness", "error", "defect",
         "Any documented field other than originating_base_num and on_scene_datetime is null.",
         "A null in a fare, a timestamp or a zone silently drops the trip from any sum, average or join that touches the field.",
         "None found in any month. The two fields with nulls have rules of their own.",
         sql=" OR ".join(f"{c} IS NULL" for c in REQUIRED),
         columns=("company", "pickup_datetime", "PULocationID", "DOLocationID", "base_passenger_fare", "driver_pay")),
    Rule("CMP-04", "Zone unknown", "completeness", "warning", "defect",
         "The pickup or dropoff zone is 264, which TLC's lookup table calls Unknown.",
         "A placeholder code is a missing value wearing a number. It joins cleanly to the lookup and lands in a borough called Unknown, so it survives every check that a null would fail.",
         "A few hundred dropoffs a month, all Uber, and no pickups. Small, but it is the pattern a completeness check has to be written to catch: a code standing in for a null.",
         sql="PULocationID = 264 OR DOLocationID = 264",
         columns=("company", "pickup_datetime", "PULocationID", "DOLocationID", "trip_miles", "base_passenger_fare")),
    Rule("CMP-05", "On-scene time equals pickup time", "completeness", "warning", "documentation gap",
         "on_scene_datetime is identical to pickup_datetime, to the second.",
         "If the on-scene time is being filled with the pickup time when it is not known, every measure of how long passengers wait at the kerb is biased towards zero.",
         "About six percent of Uber trips and a fraction of a percent of Lyft's. A driver can arrive and start the trip in the same second, but not that often for one company and not the other. It looks like a default fill; TLC does not say.",
         sql="on_scene_datetime = pickup_datetime",
         columns=("company", "request_datetime", "on_scene_datetime", "pickup_datetime", "dropoff_datetime")),

    # Uniqueness
    Rule("UNQ-01", "Duplicate record", "uniqueness", "error", "defect",
         "Two rows are identical in every field.",
         "A duplicate counts a trip and its money twice.",
         "Seventeen rows in the year, all Uber, fifteen of them in October 2025. The file carries no trip identifier, so this is the only exact test available.",
         group_sql=f"""SELECT company, day, sum(n - 1) AS failed FROM (
             SELECT t.company, t.day, count(*) AS n
             FROM trips t SEMI JOIN key_dupes k ON ({' AND '.join(f't.{c} = k.{c}' for c in TRIP_KEY)})
             GROUP BY {', '.join('t.' + c for c in REQUIRED + ['originating_base_num', 'on_scene_datetime'])}, t.company, t.day
             HAVING count(*) > 1) GROUP BY company, day"""),
    Rule("UNQ-02", "Same trip reported twice", "uniqueness", "error", "defect",
         "Two rows share company, request, pickup and dropoff times, both zones and the distance.",
         "Without a published trip identifier this is the closest thing to a key. Two rows matching on all of it are the same trip, or two trips a consumer cannot tell apart.",
         "Ninety-three rows in the year, all Uber, never more than 31 in a month. That the test has to be invented is the finding: the dictionary names no key.",
         group_sql="SELECT company, day, sum(n - 1) AS failed FROM key_dupes GROUP BY company, day"),

    # Validity
    Rule("VAL-01", "Flag outside Y and N", "validity", "error", "defect",
         "One of the five Y/N flags holds another value.",
         "A flag with a third value breaks every filter written for two.",
         "None found.",
         sql=" OR ".join(f"{c} NOT IN ('Y', 'N')" for c in FLAGS),
         columns=("company", "pickup_datetime") + tuple(FLAGS)),
    Rule("VAL-02", "Base number malformed", "validity", "error", "defect",
         "A base licence number is not a B followed by five digits.",
         "A malformed key fails the join to the licence list.",
         "None found.",
         sql=r"NOT regexp_matches(dispatching_base_num, '^B\d{5}$') OR (originating_base_num IS NOT NULL AND NOT regexp_matches(originating_base_num, '^B\d{5}$'))",
         columns=("company", "dispatching_base_num", "originating_base_num", "pickup_datetime")),
    Rule("VAL-03", "Negative fare", "validity", "warning", "business rule",
         "base_passenger_fare is below zero.",
         "A negative fare in a revenue sum understates revenue; in an average it pulls the mean below what any passenger paid.",
         "Nearly all Uber, a few thousand a month and rising through the year. The commonest value is minus the congestion surcharge, and about a quarter net the passenger's total to exactly zero: a promotion or credit has been booked into the base fare rather than shown as a discount. The exception is 25 January 2026, the day of the blizzard, with 27,000 in one day; see the driver pay rule.",
         sql="base_passenger_fare < 0",
         columns=("company", "pickup_datetime", "trip_miles", "base_passenger_fare", "congestion_surcharge", "cbd_congestion_fee", "tips", "driver_pay")),
    Rule("VAL-04", "Zero fare", "validity", "warning", "defect",
         "base_passenger_fare is exactly zero on a completed trip.",
         "Zero fares drag down the average fare and the platform's take rate.",
         "Uber's steady one to four thousand a month look like free rides. Lyft's come in bursts: 183,000 over three days, 16 to 18 August 2025, tens of thousands in four other months, and almost none in between. A promotion does not switch on and off like that; a reporting fault does.",
         sql="base_passenger_fare = 0",
         columns=("company", "pickup_datetime", "trip_miles", "trip_time", "base_passenger_fare", "driver_pay", "access_a_ride_flag")),
    Rule("VAL-05", "Negative fee, tax or tip", "validity", "error", "defect",
         "tolls, bcf, sales_tax, congestion_surcharge, airport_fee, cbd_congestion_fee or tips is below zero.",
         "A negative tax or toll is an error by definition; nothing is refunded through these fields.",
         "None found.",
         sql=" OR ".join(f"{c} < 0" for c in MONEY),
         columns=("company", "pickup_datetime") + tuple(MONEY)),
    Rule("VAL-06", "Driver pay not positive", "validity", "warning", "defect",
         "driver_pay is zero or negative.",
         "A completed trip that paid the driver nothing is either a non-trip in the trip file or a missing amount, and either way it understates driver earnings.",
         "Lyft: a steady one to two thousand a month with ordinary distances, times and fares. Uber: about six thousand a month until September 2025, a few hundred since, and 50,521 on a single day, 25 January 2026, the day of the blizzard, with zero fare, zero tax and zero pay, many sharing a pickup second. TLC's minimum pay standard does not allow a zero, so these are either missing amounts or records that are not trips.",
         sql="driver_pay <= 0",
         columns=("company", "pickup_datetime", "trip_miles", "trip_time", "base_passenger_fare", "driver_pay")),
    Rule("VAL-07", "No distance", "validity", "warning", "defect",
         "trip_miles is zero or less.",
         "Zero-mile trips pull every per-mile measure towards infinity and every average distance towards zero.",
         "A couple of thousand a month, with fares and pay attached. Some may be trips cancelled after pickup; the dictionary does not say whether those belong in the file.",
         sql="trip_miles <= 0",
         columns=("company", "pickup_datetime", "PULocationID", "DOLocationID", "trip_miles", "trip_time", "base_passenger_fare", "driver_pay")),
    Rule("VAL-08", "Surcharge outside the tariff", "validity", "warning", "defect",
         "congestion_surcharge is not 0, 0.75 or 2.75; cbd_congestion_fee is not 0 or 1.50; or airport_fee is not 0 or one of the airport fee, its shared-ride half, or its double for a trip between two airports.",
         "A surcharge that is not on the tariff was charged wrongly or recorded wrongly, and a consumer reconciling fees to the tariff cannot tell which.",
         "Almost all Lyft, and almost all one thing: from July 2025 to February 2026 about 30,000 Lyft trips a month carry an airport fee of $3.00, an amount on no tariff, and most of them start or end at Penn Station rather than an airport. It stops in March 2026. The rest are doubles and triples of the congestion fees, which look like a charge applied twice.",
         sql="congestion_surcharge NOT IN (0, 0.75, 2.75) OR cbd_congestion_fee NOT IN (0, 1.5) OR airport_fee NOT IN (0, 1.25, 2.5, 5, 1.75, 3.5, 7)",
         columns=("company", "pickup_datetime", "PULocationID", "DOLocationID", "congestion_surcharge", "cbd_congestion_fee", "airport_fee")),
    Rule("VAL-09", "Airport fee not the documented $2.50", "validity", "warning", "documentation gap",
         "airport_fee is charged and is not $2.50, the amount the data dictionary gives.",
         "A consumer validating fees against the dictionary rejects every airport trip after the change, or accepts the dictionary and misprices them.",
         "Passes on 98 percent of airport trips or more until 11 March 2026. Over the next three days the fee moves to $3.50, and from 15 March it is $3.50 on every airport trip. The dictionary, dated March 2025, still says $2.50. The data moved and the documentation did not.",
         sql="airport_fee > 0 AND airport_fee NOT IN (2.5, 1.25, 5)",
         applies="airport_fee > 0",
         columns=("company", "pickup_datetime", "PULocationID", "DOLocationID", "airport_fee")),

    Rule("VAL-10", "Schema differs from the dictionary", "validity", "error", "defect",
         "The file's columns and types differ from the March 2025 data dictionary, or from the month before.",
         "A column that appears, disappears or changes type breaks every pipeline that reads the file by position or by a fixed list.",
         "No drift in these twelve months. cbd_congestion_fee, added for January 2025, is present throughout; a consumer with older files has the drift to handle.",
         month=True),
    Rule("VAL-11", "Pickup in the hour that did not happen", "validity", "error", "defect",
         "The pickup falls between 2 and 3 in the morning on the night the clocks go forward, an hour that did not exist in New York.",
         "A timestamp in a non-existent hour cannot be converted to an instant. Anything that converts it will shift it or refuse it.",
         "A few dozen Uber trips on 8 March 2026. Impossible times, which means they were written from a clock that was not on New York time.",
         sql="month(pickup_datetime) = 3 AND isodow(pickup_datetime) = 7 AND day(pickup_datetime) BETWEEN 8 AND 14 AND hour(pickup_datetime) = 2",
         columns=("company", "request_datetime", "pickup_datetime", "dropoff_datetime", "trip_time")),
    Rule("VAL-12", "Pickup in the hour that happened twice", "validity", "warning", "documentation gap",
         "The pickup falls between 1 and 2 in the morning on the night the clocks go back, an hour New York lived through twice.",
         "The timestamps carry no zone or offset, so for these trips the instant is unknowable, and the ones that span the change come out with a dropoff before the pickup.",
         "Seventy-five thousand trips on 2 November 2025, and twelve thousand of them end before they begin. trip_time is right on every one; the dictionary never says the timestamps are local wall-clock time.",
         sql="fall_back AND hour(pickup_datetime) = 1",
         columns=("company", "pickup_datetime", "dropoff_datetime", "trip_time", "trip_miles")),

    # Consistency
    Rule("CNS-01", "Request after pickup", "consistency", "warning", "business rule",
         "request_datetime is later than pickup_datetime.",
         "Wait time is pickup minus request. When the request comes after the pickup, the wait is negative and the average wait for the month is wrong.",
         "About one percent of trips. Nine in ten of Uber's fall on a five-minute mark, and they peak before dawn, when airport trips are booked ahead: for a reserved ride the field holds the time the passenger asked to be picked up at, not the time they asked. True to its name, and wrong for a wait calculation.",
         sql="request_datetime > pickup_datetime",
         columns=("company", "request_datetime", "on_scene_datetime", "pickup_datetime", "PULocationID", "shared_request_flag")),
    Rule("CNS-02", "Driver on scene before the request", "consistency", "warning", "business rule",
         "on_scene_datetime is earlier than request_datetime.",
         "A driver cannot arrive for a request that has not been made. Any measure of response time built on these two fields goes negative.",
         "The same reserved rides as the rule before it: the driver arrives before the booked time. The fields are consistent once the meaning of request_datetime is known.",
         sql="on_scene_datetime < request_datetime",
         columns=("company", "request_datetime", "on_scene_datetime", "pickup_datetime", "PULocationID")),
    Rule("CNS-03", "Driver on scene after pickup", "consistency", "error", "defect",
         "on_scene_datetime is later than pickup_datetime.",
         "The trip started before the driver arrived. One of the two timestamps is wrong.",
         "Six to seven hundred a month, Uber, and in one month a hundred from Lyft.",
         sql="on_scene_datetime > pickup_datetime",
         columns=("company", "request_datetime", "on_scene_datetime", "pickup_datetime", "dropoff_datetime")),
    Rule("CNS-04", "Dropoff not after pickup", "consistency", "error", "defect",
         "dropoff_datetime is at or before pickup_datetime, leaving aside trips that cross the night the clocks go back.",
         "A trip of zero or negative length breaks every duration and speed calculation.",
         "Almost none once the clock change is allowed for. The clock change itself is rule VAL-12, under validity.",
         sql="dropoff_datetime <= pickup_datetime AND NOT (fall_back AND trip_time - elapsed BETWEEN 3300 AND 3900)",
         columns=("company", "pickup_datetime", "dropoff_datetime", "trip_time", "trip_miles")),
    Rule("CNS-05", "Trip time disagrees with the timestamps", "consistency", "warning", "defect",
         "trip_time differs from dropoff minus pickup by more than five minutes, after allowing for the clock changes.",
         "Two fields describe one duration. When they disagree, a consumer has to pick one and cannot know which is right.",
         "Uber: five hundred to a thousand a month. Lyft: none at all until 3 May 2026, then 82,000 in May and 58,000 in June. From 4 May a quarter of Lyft's trips report a trip_time longer than dropoff minus pickup, by anything from a second to an hour; before that day every one matched to the second. The schema did not change. What the field means did, and nothing announced it.",
         sql="least(abs(trip_time - elapsed), abs(trip_time - elapsed_ny), CASE WHEN fall_back THEN abs(trip_time - elapsed - 3600) ELSE 1e9 END) > 300",
         columns=("company", "pickup_datetime", "dropoff_datetime", "trip_time", "trip_miles")),
    Rule("CNS-06", "Driver pay exceeds fare, tips and tolls", "consistency", "warning", "business rule",
         "driver_pay is more than base_passenger_fare plus tips plus tolls.",
         "A consumer modelling the platform's take as fare minus pay gets a negative take on these trips.",
         "One Uber trip in seven and one Lyft trip in fourteen. TLC sets a minimum driver pay per mile and per minute regardless of what the passenger was charged, so on a discounted ride the driver earns more than the fare. A rule written from the dictionary alone would call every one of them an error.",
         sql="driver_pay > base_passenger_fare + tips + tolls",
         columns=("company", "pickup_datetime", "trip_miles", "trip_time", "base_passenger_fare", "tips", "tolls", "driver_pay")),
    Rule("CNS-07", "Shared match without a shared request", "consistency", "warning", "defect",
         "shared_match_flag is Y while shared_request_flag is N.",
         "A passenger cannot share a ride they did not agree to share. One flag is wrong.",
         "Lyft only, about a thousand a month. TLC's 2019 user guide already warned that Lyft's shared-ride flags overcount.",
         sql="shared_match_flag = 'Y' AND shared_request_flag = 'N'",
         columns=("company", "pickup_datetime", "shared_request_flag", "shared_match_flag", "base_passenger_fare")),
    Rule("CNS-08", "Accessible vehicle without an accessible request", "consistency", "warning", "business rule",
         "wav_match_flag is Y while wav_request_flag is N.",
         "Read as a defect, this would say a tenth of all trips have a wrong flag.",
         "A wheelchair-accessible vehicle serves ordinary requests too. The flags mean what they say and the rule was naive.",
         sql="wav_match_flag = 'Y' AND wav_request_flag = 'N'",
         columns=("company", "pickup_datetime", "wav_request_flag", "wav_match_flag")),
    Rule("CNS-09", "Airport fee away from an airport", "consistency", "error", "defect",
         "airport_fee is charged and neither zone is Newark, JFK or LaGuardia.",
         "A passenger was charged an airport fee for a trip that did not touch an airport, or the zone is wrong. Either is an error a regulator would want to see.",
         "Uber: a few hundred to fifteen hundred a month. Lyft: about 30,000 a month from July 2025 to February 2026, most of them a $3.00 fee on trips that start or end at Penn Station, then almost none. A fee that is not an airport fee was being reported in the airport fee column: a misfielded value, in the language of the catalog.",
         sql=f"airport_fee > 0 AND PULocationID NOT IN {AIRPORT_ZONES} AND DOLocationID NOT IN {AIRPORT_ZONES}",
         applies="airport_fee > 0",
         columns=("company", "pickup_datetime", "PULocationID", "DOLocationID", "airport_fee", "base_passenger_fare")),
    Rule("CNS-10", "Airport trip without the fee", "consistency", "warning", "defect",
         "A zone is Newark, JFK or LaGuardia and airport_fee is zero.",
         "Fees that should have been collected were not, or were not recorded.",
         "Under one percent of airport trips, both companies. There may be exemptions; the dictionary lists none.",
         sql=f"airport_fee = 0 AND (PULocationID IN {AIRPORT_ZONES} OR DOLocationID IN {AIRPORT_ZONES})",
         applies=f"PULocationID IN {AIRPORT_ZONES} OR DOLocationID IN {AIRPORT_ZONES}",
         columns=("company", "pickup_datetime", "PULocationID", "DOLocationID", "airport_fee", "base_passenger_fare")),
    Rule("CNS-11", "No sales tax on an in-city trip", "consistency", "warning", "documentation gap",
         "sales_tax is zero on a trip with a positive fare that starts and ends inside the city.",
         "Sales tax is a fixed rate on the fare. A zero on a taxable trip is tax not collected, not recorded, or an exemption the consumer does not know about.",
         "Trips to Newark and outside the city are left out because interstate trips are not taxed, and after that about 85,000 a month remain, two thirds of them Lyft. Nothing TLC publishes says which trips are exempt.",
         sql=f"sales_tax = 0 AND base_passenger_fare > 0 AND PULocationID NOT IN (1, 264, 265) AND DOLocationID NOT IN (1, 264, 265)",
         columns=("company", "pickup_datetime", "PULocationID", "DOLocationID", "base_passenger_fare", "sales_tax", "bcf", "access_a_ride_flag")),
    Rule("CNS-12", "Passenger total below zero", "consistency", "error", "defect",
         "The fare plus every fee, tax and tip comes to less than zero.",
         "The passenger was paid to ride. A credit larger than the ride it was applied to has been booked into the trip.",
         "A couple of thousand a month, almost all Uber. The negative-fare rule explains most negative fares; these are the ones a promotion does not.",
         sql="base_passenger_fare + tolls + bcf + sales_tax + congestion_surcharge + airport_fee + cbd_congestion_fee + tips < 0",
         columns=("company", "pickup_datetime", "trip_miles", "base_passenger_fare", "tolls", "sales_tax", "congestion_surcharge", "cbd_congestion_fee", "tips", "driver_pay")),

    # Accuracy
    Rule("ACC-01", "Destination outside the city", "accuracy", "warning", "business rule",
         "The pickup or dropoff zone is 265, Outside of NYC.",
         "Every trip to New Jersey, Westchester or Long Island lands in one zone. A consumer mapping demand sees a spike in nowhere; one splitting in-state from out-of-state tax cannot.",
         "About a million trips a month, almost all dropoffs. The value is correct and coarse: the zone system stops at the city line. ISO 25012 would call this precision rather than accuracy.",
         sql="PULocationID = 265 OR DOLocationID = 265",
         columns=("company", "pickup_datetime", "PULocationID", "DOLocationID", "trip_miles", "sales_tax")),
    Rule("ACC-02", "Trip counts disagree with TLC's own aggregates", "accuracy", "error", "defect",
         "The month's trips in the file differ from the FHV Base Aggregate Report on NYC Open Data, per company, or from TLC's monthly indicators in total, by more than half a percent.",
         "Two TLC publications of the same month should agree. When they do not, a consumer citing one is contradicted by the other, and one of them is missing trips.",
         "Ten of twelve months match the aggregate report to the trip, both companies. January 2026 has 100,927 Uber trips the aggregate does not count, and half of that gap is visible in the file: 50,521 Uber records on 25 January, the day of the blizzard, with zero fare and zero driver pay. June 2026 is short about 454,000 against the indicators, which is the size of Lyft's missing week.",
         month=True),

    # Reasonability
    Rule("RSN-01", "Daily volume drop", "reasonability", "warning", "defect",
         "A company's trips on a day fall more than 25 percent below the median of the same weekday in the surrounding eight weeks.",
         "A day that is short of trips is either a real event or a short file, and a consumer has to know which before using the month.",
         "The blizzards of 25 January and 23 February 2026 explain two. The week of 8 June 2026 is Lyft alone, down a third at every hour and in every borough with Uber untouched, and the month's total is short by about the same amount against TLC's indicators: a partial submission, not a quiet week.",
         month=True),
    Rule("RSN-02", "Trip under a minute", "reasonability", "warning", "documentation gap",
         "trip_time is below 60 seconds.",
         "A trip file that also holds cancellations makes every count of trips too high.",
         "A couple of thousand a month: a few hundredths of a mile, a fare around seven dollars and driver pay around four. They look like cancellation fees, which the dictionary neither includes nor excludes.",
         sql="trip_time < 60",
         columns=("company", "pickup_datetime", "dropoff_datetime", "trip_miles", "trip_time", "base_passenger_fare", "driver_pay")),
    Rule("RSN-03", "Implausible speed", "reasonability", "error", "defect",
         "Distance over time works out above 80 miles an hour.",
         "A trip faster than the road allows has a wrong distance or a wrong time, and any per-mile or per-minute figure built on it is wrong too.",
         "About fifteen a month. Small, but each one is certainly wrong, which is what a reasonableness check is for.",
         sql="trip_time > 0 AND trip_miles / trip_time * 3600 > 80",
         columns=("company", "pickup_datetime", "dropoff_datetime", "PULocationID", "DOLocationID", "trip_miles", "trip_time")),
    Rule("RSN-04", "Extreme trip", "reasonability", "warning", "business rule",
         "trip_miles is over 100 or trip_time is over five hours.",
         "Outliers dominate averages. A consumer who does not know they are real will trim them; one who does not know they exist will report a mean they distort.",
         "A few thousand a month. Trips to the Hamptons and Philadelphia are real, and the driver pay on them says so. Outliers to be aware of, not errors.",
         sql="trip_miles > 100 OR trip_time > 5 * 3600",
         columns=("company", "pickup_datetime", "dropoff_datetime", "PULocationID", "DOLocationID", "trip_miles", "trip_time", "base_passenger_fare", "driver_pay")),
    Rule("RSN-05", "Fare far below the driver's pay", "reasonability", "warning", "documentation gap",
         "A trip over a mile is priced under fifty cents a mile.",
         "A fare this far below the going rate drags down every average revenue figure built on base_passenger_fare, and a consumer cannot tell whether the trip was discounted or the number is wrong.",
         "4,893 trips in the year, 98 percent of them Uber, between 188 and 920 a month. In June 2026, the month checked closely, the driver was paid more than the passenger on 97 percent of them: the signature of a promotion or a corporate rate, where the passenger's price is net of something the file does not carry. The dictionary never says whether base_passenger_fare is before or after a discount, so the record may be right and nothing published lets a consumer tell.",
         sql="trip_miles > 1 AND base_passenger_fare > 0 AND base_passenger_fare / trip_miles < 0.5",
         applies="trip_miles > 1 AND base_passenger_fare > 0",
         columns=("company", "pickup_datetime", "trip_miles", "trip_time", "base_passenger_fare", "driver_pay")),
    Rule("RSN-06", "Fare far above the going rate", "reasonability", "warning", "business rule",
         "A trip over a mile is priced above fifty dollars a mile.",
         "Per-mile pricing is how most people sanity check a fare, and a rate this far out of band looks like a wrong distance until it is explained.",
         "54,487 in the year, nine in ten of them trips under two miles. These fares are time as well as distance, so a short trip crawling for twenty minutes at a surged rate prices far above any per-mile expectation. December 2025 holds a third of the year on its own, most of it on the 10th and the 11th, days when the trip count was perfectly ordinary: a demand squeeze, not a reporting fault. The rule is naive rather than the records wrong, and worth keeping because it finds the short expensive trips a distance-only check misses.",
         sql="trip_miles > 1 AND base_passenger_fare > 0 AND base_passenger_fare / trip_miles > 50",
         applies="trip_miles > 1 AND base_passenger_fare > 0",
         columns=("company", "pickup_datetime", "trip_miles", "trip_time", "base_passenger_fare", "driver_pay")),
    Rule("RSN-07", "Two hours from request to pickup", "reasonability", "warning", "business rule",
         "pickup_datetime is more than two hours after request_datetime.",
         "Time from request to pickup is the service level this data is usually read for, and a handful of multi-hour waits pulls an average that everything else keeps near five minutes.",
         "1,486 trips in the year, and all but eight of them Uber. Three in five have a request time landing on an exact minute, against three in a hundred trips overall, and on a third the driver was on scene before the request: both are the signature of a booked ride, where request_datetime is when the trip was scheduled rather than when someone stood on a kerb. Lyft reports eight in twelve months, so this is one company's reporting practice as much as a rider's behaviour. The wait is a reservation, so the rule is naive, not the data wrong.",
         sql="pickup_datetime > request_datetime + INTERVAL 2 HOUR",
         columns=("company", "request_datetime", "on_scene_datetime", "pickup_datetime", "dropoff_datetime", "trip_miles")),

    # Timeliness
    Rule("TML-01", "Published late", "timeliness", "warning", "documentation gap",
         "The file was published more than 62 days after the end of its month.",
         "A consumer plans around the publication schedule the publisher states. TLC's data page says about two months; its user guide says every six.",
         "Every month here arrived within five weeks of month end, and December 2025 within eight. Earlier than either document promises, and on no fixed day: the last-modified date is the only schedule there is.",
         month=True),
    Rule("TML-02", "Aggregate report behind the trip file", "timeliness", "warning", "defect",
         "The FHV Base Aggregate Report has no row for a month whose trip file is published.",
         "The two publications are consumed together. A month present in one and absent from the other cannot be reconciled until the second catches up.",
         "June 2026 was in the trip file for seven weeks before this build and still absent from the aggregate report.",
         month=True),

    # Integrity
    Rule("INT-01", "Zone not in the lookup table", "integrity", "error", "defect",
         "PULocationID or DOLocationID is not a LocationID in TLC's taxi zone lookup.",
         "A zone id without a zone fails the join that gives every trip a borough and a name.",
         "None found. Every trip joins.",
         sql="PULocationID NOT IN (SELECT LocationID FROM zones) OR DOLocationID NOT IN (SELECT LocationID FROM zones)",
         columns=("company", "pickup_datetime", "PULocationID", "DOLocationID")),
    Rule("INT-02", "Pickup outside the file's month", "integrity", "error", "defect",
         "The pickup date is in a different month from the file.",
         "A trip in the wrong month is counted in the wrong period, or twice, or never, depending on how the files are stitched together.",
         "None found in these twelve months. Each file holds exactly the trips that began in its month.",
         sql="strftime(pickup_datetime, '%Y-%m') <> '{month}'",
         columns=("company", "request_datetime", "pickup_datetime", "dropoff_datetime")),
    Rule("INT-03", "Licence code outside the documented list", "integrity", "error", "defect",
         "hvfhs_license_num is not one of the four codes the dictionary lists.",
         "A code the dictionary does not know cannot be mapped to a company.",
         "None found. Only Uber and Lyft appear; Juno and Via, still in the dictionary, have not dispatched a trip in years.",
         month=True),

]

RULE_BY_ID = {r.id: r for r in RULES}
ROW_RULES = [r for r in RULES if r.sql or r.group_sql]
MONTH_RULES = [r for r in RULES if r.month]

# What TLC's documentation says and the files do not, or the other way round. Some of
# these have a rule above; the rest are findings about the documents themselves.
DOCUMENTATION = [
    {"where": "Trip record user guide (September 2019)", "says": "files are CSV", "data": "every file is parquet, as the data page says"},
    {"where": "Trip record user guide (September 2019)", "says": "trip records are updated every six months", "data": "the data page says monthly, about two months behind; the files arrive three to five weeks after month end"},
    {"where": "Trip record user guide (September 2019)", "says": "location ids run from 1 to 263", "data": "264 (Unknown) and 265 (Outside of NYC) are in the lookup table and on a million trips a month"},
    {"where": "HVFHV data dictionary (March 2025)", "says": "on_scene_datetime applies to accessible vehicles only", "data": "every trip has one", "rule": "CMP-02"},
    {"where": "HVFHV data dictionary (March 2025)", "says": "the airport fee is $2.50", "data": "$3.50 on every airport trip since 15 March 2026; and for eight months Lyft reported a $3.00 fee at Penn Station in the same column", "rule": "VAL-09"},
    {"where": "HVFHV data dictionary (March 2025)", "says": "request_datetime is when the passenger requested to be picked up", "data": "for a reserved ride it is the time they asked to be picked up at, which can be after the pickup", "rule": "CNS-01"},
    {"where": "HVFHV data dictionary (March 2025)", "says": "trip_time is total time in seconds for the passenger trip", "data": "Uber's equals dropoff minus pickup; so did Lyft's until 4 May 2026, and since then a quarter of Lyft's run longer", "rule": "CNS-05"},
    {"where": "HVFHV data dictionary (March 2025)", "says": "driver_pay is total driver pay, net of commission, surcharges and taxes", "data": "it exceeds the fare on a tenth of trips because TLC's minimum pay standard sets it per mile and per minute; the word incentive does not appear", "rule": "CNS-06"},
    {"where": "HVFHV data dictionary (March 2025)", "says": "nothing about time zones", "data": "timestamps are New York wall-clock time with no offset, ambiguous for an hour each November", "rule": "VAL-12"},
    {"where": "HVFHV data dictionary (March 2025)", "says": "nothing about a trip identifier", "data": "there is none; uniqueness can only be tested on a combination of fields", "rule": "UNQ-02"},
    {"where": "HVFHV data dictionary (March 2025)", "says": "nothing about when sales tax applies", "data": "zero on interstate trips and on a hundred thousand in-city trips a month", "rule": "CNS-11"},
    {"where": "HVFHV data dictionary (March 2025)", "says": "Juno (HV0002) and Via (HV0004) are licensees", "data": "neither has a trip in the files; only Uber and Lyft do", "rule": "INT-03"},
    {"where": "FHV Base Aggregate Report (NYC Open Data)", "says": "base_license_number is the TLC licence number of the base", "data": "Uber's and Lyft's rows carry the words UBER and LYFT, not licence numbers, so the report cannot be joined to the trip files on the key"},
    {"where": "FHV Base Aggregate Report (NYC Open Data)", "says": "month is the number of the week in a given year", "data": "it is the month"},
]


def registry():
    """The registry as plain data, for rules.json."""
    return {
        "dimensions": DIMENSIONS,
        "verdicts": list(VERDICTS),
        "rules": [
            {"id": r.id, "name": r.name, "dimension": r.dimension, "severity": r.severity, "verdict": r.verdict,
             "test": r.test, "why": r.why, "note": r.note, "grain": r.grain, "applies": r.applies != "TRUE",
             # applies_sql is the denominator: the trips the rule is checked against. The page
             # shows it next to the predicate so a reader can see both halves of the rate.
             "applies_sql": r.applies if r.applies != "TRUE" else "",
             "sql": r.sql or r.group_sql, "columns": list(r.columns)}
            for r in RULES
        ],
        "documentation": DOCUMENTATION,
    }
