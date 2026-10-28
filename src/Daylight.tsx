import { useMemo } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { Environment, Sky } from "@react-three/drei";
import { daylight, sunDirection, sunPosition } from "./sun";

const warm = new THREE.Color("#ff9a5a");
const white = new THREE.Color("#fff4e2");

// sky, image-based light and a shadow-casting sun for a given moment
// shadows only need to be sharp around the viewer: a 50 m box that follows the camera
const shadowRadius = 25;
const snap = 2;

export function Daylight({ date }: { date: Date }) {
  const sun = sunPosition(date);
  const dir = sunDirection(sun);
  const height = Math.sin(sun.altitude);
  const day = daylight(sun.altitude);

  const light = useMemo(() => {
    const l = new THREE.DirectionalLight();
    const cam = l.shadow.camera;
    cam.left = cam.bottom = -shadowRadius;
    cam.right = cam.top = shadowRadius;
    cam.near = 1;
    cam.far = shadowRadius * 6;
    cam.updateProjectionMatrix();
    l.shadow.mapSize.set(4096, 4096);
    l.shadow.bias = -0.0002;
    l.shadow.normalBias = 0.02;
    return l;
  }, []);
  light.color.copy(warm).lerp(white, THREE.MathUtils.smoothstep(height, 0, 0.5));
  light.intensity = 4 * day;
  light.castShadow = day > 0;

  useFrame(({ camera }) => {
    // snapped to whole steps so shadow edges do not shimmer while walking
    const t = light.target.position;
    t.set(
      Math.round(camera.position.x / snap) * snap,
      0,
      Math.round(camera.position.z / snap) * snap,
    );
    light.position.set(
      t.x + dir[0] * shadowRadius * 3,
      t.y + dir[1] * shadowRadius * 3,
      t.z + dir[2] * shadowRadius * 3,
    );
  });

  const sky = (
    <Sky
      distance={450000}
      sunPosition={dir}
      turbidity={6}
      rayleigh={1.5}
      mieCoefficient={0.005}
      mieDirectionalG={0.8}
    />
  );

  return (
    <>
      {sky}
      {/* re-render the environment only when the sun moves noticeably */}
      <Environment
        key={`${dir.map((v) => v.toFixed(2)).join()}`}
        resolution={128}
        environmentIntensity={0.1 + 0.5 * day}
      >
        {sky}
      </Environment>
      {/* moonlight floor so nights stay readable */}
      <hemisphereLight args={["#8fa6d6", "#1d2230", 0.25 * (1 - day)]} />
      <primitive object={light} />
      <primitive object={light.target} />
    </>
  );
}
