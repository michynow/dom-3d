import {
  Component,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Canvas } from "@react-three/fiber";
import type { PointerLockControls as PointerLockControlsImpl } from "three-stdlib";
import { House, forgetHouse, type Collider } from "./House";
import { Player } from "./Player";
import { Daylight } from "./Daylight";
import { maps, type HouseMap } from "./maps";
import { atMinute, daylight, formatMinute, sunPosition, sunTimes } from "./sun";

const formatMB = (bytes: number) => `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

export function App() {
  const [map, setMap] = useState<HouseMap | null>(null);
  const [collider, setCollider] = useState<Collider | null>(null);
  const [locked, setLocked] = useState(false);
  const [visited, setVisited] = useState(false);
  const [progress, setProgress] = useState({ ratio: 0, text: "" });
  const [failed, setFailed] = useState(false);
  const [day, setDay] = useState(() => new Date().toLocaleDateString("sv-SE"));
  const times = useMemo(() => sunTimes(day), [day]);
  const presets = useMemo(
    () => [
      { label: "Rano", minute: times.sunrise + 90 },
      { label: "Południe", minute: times.noon },
      {
        label: "Popołudnie",
        minute: Math.round(times.noon + (times.sunset - times.noon) * 0.55),
      },
      { label: "Wieczór", minute: times.sunset - 25 },
    ],
    [times],
  );
  const [minute, setMinute] = useState(() => {
    const t = sunTimes(new Date().toLocaleDateString("sv-SE"));
    return Math.round(t.noon + (t.sunset - t.noon) * 0.55);
  });
  const controlsRef = useRef<PointerLockControlsImpl | null>(null);

  const pick = (next: HouseMap | null) => {
    if (map) forgetHouse(map);
    setCollider(null);
    setVisited(false);
    setFailed(false);
    setProgress({ ratio: 0, text: "Wczytywanie modelu…" });
    setMap(next);
  };

  const onProgress = useCallback((event: ProgressEvent) => {
    if (!event.lengthComputable) {
      setProgress({ ratio: 0, text: `Wczytywanie modelu… ${formatMB(event.loaded)}` });
      return;
    }
    const ratio = event.loaded / event.total;
    setProgress({
      ratio,
      text: `Wczytywanie modelu… ${Math.round(ratio * 100)}% · ${formatMB(event.loaded)} / ${formatMB(event.total)}`,
    });
  }, []);

  const onLockChange = useCallback((value: boolean) => {
    setLocked(value);
    if (value) setVisited(true);
  }, []);

  // T while walking cycles through the day presets
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!locked || event.code !== "KeyT") return;
      const next = presets.find((p) => p.minute > minute + 1) ?? presets[0];
      setMinute(next.minute);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [locked, presets, minute]);

  const date = atMinute(day, minute);
  const night = 1 - daylight(sunPosition(date).altitude);

  return (
    <>
      <Canvas
        shadows
        dpr={[1, 2]}
        camera={{ fov: 75, near: 0.1, far: 500, position: [0, 20, 40] }}
        gl={{ antialias: true, toneMappingExposure: 0.8 }}
      >
        <Daylight date={date} />
        {map && (
          <ErrorBoundary key={map.id} onError={() => setFailed(true)}>
            <Suspense fallback={null}>
              <House
                map={map}
                night={night}
                onProgress={onProgress}
                onReady={setCollider}
              />
            </Suspense>
          </ErrorBoundary>
        )}
        {map && collider && (
          <Player
            map={map}
            collider={collider}
            controlsRef={controlsRef}
            onLockChange={onLockChange}
          />
        )}
      </Canvas>

      <div className="welcome" hidden={locked}>
        <div className="welcome__panel">
          <p className="welcome__eyebrow">Wirtualny spacer</p>
          <h1 className="welcome__title">{map?.name ?? "Wybierz dom"}</h1>

          {!map ? (
            <ul className="maps">
              {maps.map((m) => (
                <li key={m.id}>
                  <button type="button" className="map" onClick={() => pick(m)}>
                    {m.thumb ? (
                      <img className="map__thumb" src={m.thumb} alt="" />
                    ) : (
                      <span className="map__thumb" />
                    )}
                    <span>
                      <span className="map__name">{m.name}</span>
                      <span className="map__meta">{m.meta}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="welcome__walk">
              {!collider && !failed && (
                <div
                  className="welcome__progress"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(progress.ratio * 100)}
                  aria-label="Postęp wczytywania modelu"
                >
                  <span
                    className="welcome__bar"
                    style={{ width: `${Math.round(progress.ratio * 100)}%` }}
                  />
                </div>
              )}
              <p className="welcome__status">
                {failed
                  ? "Nie udało się wczytać modelu. Wybierz dom ponownie."
                  : !collider
                    ? progress.text
                    : visited
                      ? "Kliknij, aby wrócić do spaceru."
                      : "Model gotowy."}
              </p>
              <div className="welcome__actions">
                <button
                  type="button"
                  id="enter"
                  className="welcome__enter"
                  disabled={!collider}
                >
                  {visited ? "Wróć do spaceru" : "Wejdź do domu"}
                </button>
                <button
                  type="button"
                  className="welcome__change"
                  onClick={() => pick(null)}
                >
                  Zmień dom
                </button>
              </div>
            </div>
          )}

          <fieldset className="daytime">
            <legend className="welcome__eyebrow">Pora dnia</legend>
            <div className="daytime__presets">
              {presets.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  className="daytime__preset"
                  aria-pressed={p.minute === minute}
                  onClick={() => setMinute(p.minute)}
                >
                  {p.label}
                  <span className="daytime__time">{formatMinute(p.minute)}</span>
                </button>
              ))}
            </div>
            <label className="daytime__row">
              <span>Godzina {formatMinute(minute)}</span>
              <input
                type="range"
                min={0}
                max={1439}
                step={5}
                value={minute}
                onChange={(e) => setMinute(Number(e.target.value))}
              />
            </label>
            <label className="daytime__row">
              <span>Data</span>
              <input
                type="date"
                value={day}
                required
                onChange={(e) => e.target.value && setDay(e.target.value)}
              />
            </label>
            <p className="welcome__hint">
              Wschód {formatMinute(times.sunrise)} · zachód{" "}
              {formatMinute(times.sunset)} (centralna Polska)
            </p>
          </fieldset>

          <p className="welcome__hint">
            WASD — ruch. Mysz — rozglądanie. Shift — bieg. Spacja — skok. T —
            pora dnia. Esc — menu.
          </p>
        </div>
      </div>
    </>
  );
}

class ErrorBoundary extends Component<
  { children: ReactNode; onError: () => void },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  componentDidCatch() {
    this.props.onError();
  }
  render() {
    return this.state.error ? null : this.props.children;
  }
}
