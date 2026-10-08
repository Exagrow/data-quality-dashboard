// The arithmetic this dashboard does on TLC's monthly summaries. Formatting,
// colours and chrome come from the kit (src/kit/); what is left here is the
// part that knows what a trip record is.

// Add up the measure columns of a set of summary rows.
export function totals(data) {
  const t = {trips: 0, fares: 0, driver_pay: 0, tips: 0, rider_total: 0, miles: 0, trip_seconds: 0, wait_seconds: 0, wait_trips: 0, airport_trips: 0, shared_trips: 0, wav_trips: 0};
  for (const d of data) for (const k in t) t[k] += d[k] ?? 0;
  return t;
}

// The ratios the page reports, from totals().
export function metrics(t) {
  return {
    trips: t.trips,
    fares: t.fares,
    driverPay: t.driver_pay,
    platformShare: t.fares ? 1 - t.driver_pay / t.fares : NaN,
    avgFare: t.trips ? t.fares / t.trips : NaN,
    avgWait: t.wait_trips ? t.wait_seconds / t.wait_trips : NaN,
    avgMiles: t.trips ? t.miles / t.trips : NaN,
    avgMinutes: t.trips ? t.trip_seconds / t.trips / 60 : NaN,
    tipRate: t.fares ? t.tips / t.fares : NaN,
    airportShare: t.trips ? t.airport_trips / t.trips : NaN
  };
}
