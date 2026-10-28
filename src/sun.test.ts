// node src/sun.test.ts
import assert from "node:assert/strict";
import { sunPosition } from "./sun.ts";

const deg = (r: number) => (r * 180) / Math.PI;

// Warsaw-ish (52°N 19°E), summer solstice, solar noon ≈ 10:44 UTC: altitude 90 - 52 + 23.44 ≈ 61.4°, due south
const noon = sunPosition(new Date("2026-06-21T10:44:00Z"));
assert.ok(Math.abs(deg(noon.altitude) - 61.4) < 0.5, `alt ${deg(noon.altitude)}`);
assert.ok(Math.abs(deg(noon.azimuth) - 180) < 2, `az ${deg(noon.azimuth)}`);

// winter solstice noon: 90 - 52 - 23.44 ≈ 14.6°
const winter = sunPosition(new Date("2026-12-21T10:44:00Z"));
assert.ok(Math.abs(deg(winter.altitude) - 14.6) < 0.5, `alt ${deg(winter.altitude)}`);

// equinox morning: sun in the east (azimuth < 180), below 30°
const morning = sunPosition(new Date("2026-03-20T06:00:00Z"));
assert.ok(deg(morning.azimuth) > 60 && deg(morning.azimuth) < 120, `az ${deg(morning.azimuth)}`);

console.log("sun ok");
