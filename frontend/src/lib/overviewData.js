export function budapestToday(now = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Budapest", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

const numeric = value => typeof value === "number" && Number.isFinite(value);
const validDate = value => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;

export function overviewData(data, days, today = budapestToday()) {
  const start = new Date(`${today}T12:00:00Z`);
  start.setUTCDate(start.getUTCDate() - days + 1);
  const from = start.toISOString().slice(0, 10);
  const inRange = item => validDate(item?.date) && item.date >= from && item.date <= today;
  const known = Array.isArray(data?.sessions) && data.sessions.every(item => validDate(item?.date));
  const sessions = known ? data.sessions.filter(inRange) : [];
  const sum = key => known && sessions.every(item => numeric(item[key]) && item[key] >= 0)
    ? sessions.reduce((total, item) => total + item[key], 0) : null;
  return {
    from, today, known, sessions, minutes: sum("durationMin"), load: sum("load"),
    readiness: data?.today === today && numeric(data?.readiness) && data.readiness >= 0 && data.readiness <= 100 ? data.readiness : null,
    points: (Array.isArray(data?.trends) ? data.trends : []).filter(inRange).map(item => ({
      date: item.date,
      ctl: numeric(item.ctl) ? item.ctl : null,
      atl: numeric(item.atl) ? item.atl : null,
      tsb: numeric(item.tsb) ? item.tsb : null,
    })).sort((a, b) => a.date.localeCompare(b.date)),
  };
}
