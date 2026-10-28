// Solar position (SunCalc / Astronomical Algorithms simplified, ~0.1° accuracy).
// Default site: central Poland. Model space: north = -Z, east = +X (Blender -Y front faces south).
export const SITE = { lat: 52.0, lon: 19.0 };

const rad = Math.PI / 180;
const dayMs = 86_400_000;
const J2000 = 10_957.5; // 2000-01-01 12:00 UTC in days since the Unix epoch

export type SunPosition = {
  altitude: number; // radians above the horizon
  azimuth: number; // radians from north, clockwise (east = π/2)
};

export function sunPosition(
  date: Date,
  lat = SITE.lat,
  lon = SITE.lon,
): SunPosition {
  const d = date.getTime() / dayMs - J2000;
  const M = rad * (357.5291 + 0.98560028 * d);
  const C =
    rad *
    (1.9148 * Math.sin(M) +
      0.02 * Math.sin(2 * M) +
      0.0003 * Math.sin(3 * M));
  const L = M + C + rad * 102.9372 + Math.PI;
  const e = rad * 23.4397;
  const dec = Math.asin(Math.sin(e) * Math.sin(L));
  const ra = Math.atan2(Math.sin(L) * Math.cos(e), Math.cos(L));
  const H = rad * (280.16 + 360.9856235 * d) + rad * lon - ra;
  const phi = rad * lat;
  const altitude = Math.asin(
    Math.sin(phi) * Math.sin(dec) +
      Math.cos(phi) * Math.cos(dec) * Math.cos(H),
  );
  const fromSouth = Math.atan2(
    Math.sin(H),
    Math.cos(H) * Math.sin(phi) - Math.tan(dec) * Math.cos(phi),
  );
  return { altitude, azimuth: fromSouth + Math.PI };
}

// unit vector towards the sun in model space
export function sunDirection({ altitude, azimuth }: SunPosition) {
  return [
    Math.cos(altitude) * Math.sin(azimuth),
    Math.sin(altitude),
    -Math.cos(altitude) * Math.cos(azimuth),
  ] as [number, number, number];
}

export const atMinute = (day: string, minute: number) => {
  const date = new Date(`${day}T00:00:00`);
  date.setMinutes(minute);
  return date;
};

// sunrise / solar noon / sunset as minutes of the local day; minute scan is plenty for a UI
export function sunTimes(day: string) {
  const horizon = -0.833 * rad; // refraction + solar disc
  let sunrise = -1;
  let sunset = -1;
  let noon = 720;
  let best = -Infinity;
  let prev = sunPosition(atMinute(day, 0)).altitude;
  for (let m = 1; m < 1440; m++) {
    const alt = sunPosition(atMinute(day, m)).altitude;
    if (prev < horizon && alt >= horizon) sunrise = m;
    if (prev >= horizon && alt < horizon) sunset = m;
    if (alt > best) [best, noon] = [alt, m];
    prev = alt;
  }
  return { sunrise, noon, sunset };
}

export const formatMinute = (minute: number) =>
  `${Math.floor(minute / 60)}:${String(minute % 60).padStart(2, "0")}`;

// 0 at night, 1 in daylight; civil dusk (sun a few degrees under the horizon) fades between
export const daylight = (altitude: number) => {
  const t = Math.min(1, Math.max(0, (Math.sin(altitude) + 0.05) / 0.2));
  return t * t * (3 - 2 * t);
};
