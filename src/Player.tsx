import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { PointerLockControls } from "@react-three/drei";
import type { PointerLockControls as PointerLockControlsImpl } from "three-stdlib";
import type { Collider } from "./House";
import type { HouseMap } from "./maps";
import { TouchControls, isTouch } from "./touch-controls";

const walkSpeed = 5;
const sprintSpeed = 12;
const eyeHeight = 1.6;
// wall probes look ~0.4 m ahead, so they must clear two risers (2 × 0.185 m on Wojtek's stairs)
const stepHeight = 0.45;
const stepUpSpeed = 12;
// 0.9 m doorways leave 0.78 m between the frames: a slimmer body passes without pixel-perfect aiming
const playerRadius = 0.28;
const gravity = 22;
const jumpSpeed = 7.5;
const bodySampleCount = 5;
const sideSpread = playerRadius * 0.65;
// |normal.y| above this = walkable surface, below = wall
const floorNormalY = 0.7;

const down = new THREE.Vector3(0, -1, 0);
const up = new THREE.Vector3(0, 1, 0);
const front = new THREE.Vector3();
const right = new THREE.Vector3();
const moveDir = new THREE.Vector3();
const origin = new THREE.Vector3();
const probe = new THREE.Vector3();
const axisDir = new THREE.Vector3();
const sideDir = new THREE.Vector3();
const nudge = new THREE.Vector3();
const lateral = new THREE.Vector3();

const keyMap: Record<string, keyof typeof initialKeys> = {
  KeyW: "forward",
  ArrowUp: "forward",
  KeyS: "backward",
  ArrowDown: "backward",
  KeyA: "left",
  ArrowLeft: "left",
  KeyD: "right",
  ArrowRight: "right",
  ShiftLeft: "sprint",
  ShiftRight: "sprint",
};
const initialKeys = {
  forward: false,
  backward: false,
  left: false,
  right: false,
  sprint: false,
  jump: false,
  use: false,
};

const doorReach = 2.2;
const doorSpeed = 1.6; // full swing in ~0.6 s
const ease = (t: number) => t * t * (3 - 2 * t);
const doorCenter = new THREE.Vector3();
const toDoor = new THREE.Vector3();
const lookDir = new THREE.Vector3();
const doorBox = new THREE.Box3();

export function Player({
  map,
  collider,
  controlsRef,
  onLockChange,
}: {
  map: HouseMap;
  collider: Collider;
  controlsRef: RefObject<PointerLockControlsImpl | null>;
  onLockChange: (locked: boolean) => void;
}) {
  const camera = useThree((s) => s.camera);
  const raycaster = useRef(new THREE.Raycaster()).current;
  const keys = useRef({ ...initialKeys }).current;
  const state = useRef({ velocityY: 0, grounded: true }).current;
  const touchRef = useRef<TouchControls | null>(null);

  // phones: Enter starts the on-screen twin-stick controls instead of pointer lock
  useEffect(() => {
    if (!isTouch) return;
    const touch = new TouchControls(camera);
    touchRef.current = touch;
    const enter = document.querySelector("#enter");
    const start = () => {
      document.documentElement.requestFullscreen?.().catch(() => {});
      touch.enable();
    };
    const lock = () => onLockChange(true);
    const unlock = () => onLockChange(false);
    enter?.addEventListener("click", start);
    touch.addEventListener("lock", lock);
    touch.addEventListener("unlock", unlock);
    return () => {
      enter?.removeEventListener("click", start);
      touch.removeEventListener("lock", lock);
      touch.removeEventListener("unlock", unlock);
      touch.dispose();
      touchRef.current = null;
    };
  }, [camera, onLockChange]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent, pressed: boolean) => {
      if (event.code === "Space") {
        if (pressed) keys.jump = true;
        event.preventDefault();
        return;
      }
      if (event.code === "KeyE") {
        if (pressed && !event.repeat) keys.use = true;
        return;
      }
      const key = keyMap[event.code];
      if (key) keys[key] = pressed;
    };
    const down = (e: KeyboardEvent) => onKey(e, true);
    const up = (e: KeyboardEvent) => onKey(e, false);
    document.addEventListener("keydown", down);
    document.addEventListener("keyup", up);
    return () => {
      document.removeEventListener("keydown", down);
      document.removeEventListener("keyup", up);
    };
  }, [keys]);

  // per-door swing state: t 0 = closed, 1 = open
  const doors = useRef<{ obj: THREE.Object3D; angle: number; t: number; target: number }[]>([]);
  useLayoutEffect(() => {
    doors.current = collider.doors.map((obj) => ({
      obj,
      angle: obj.userData.openAngle as number,
      t: 0,
      target: 0,
    }));
  }, [collider]);

  const castRay = (from: THREE.Vector3, dir: THREE.Vector3, far: number) => {
    raycaster.set(from, dir);
    raycaster.near = 0;
    raycaster.far = far;
    raycaster.firstHitOnly = true;
    const hit = raycaster.intersectObject(collider.mesh, false)[0] ?? null;
    if (collider.doors.length === 0) return hit;
    // door leaves move, so they are not in the static BVH; a few dozen plain meshes are cheap to test
    const door = raycaster.intersectObjects(collider.doors, true)[0];
    if (door && (!hit || door.distance < hit.distance)) {
      // leaf normals are in object space; walls only need the "is it vertical" test downstream
      door.face = door.face ?? null;
      if (door.face) door.face.normal = door.face.normal.clone().transformDirection(door.object.matrixWorld);
      return door;
    }
    return hit;
  };

  // toggle the closest door in front of the camera within reach
  const useDoor = () => {
    camera.getWorldDirection(lookDir);
    lookDir.y = 0;
    lookDir.normalize();
    let best: (typeof doors.current)[number] | null = null;
    let bestDist = doorReach;
    for (const d of doors.current) {
      doorBox.setFromObject(d.obj).getCenter(doorCenter);
      toDoor.subVectors(doorCenter, camera.position);
      toDoor.y = 0;
      const dist = toDoor.length();
      if (dist < bestDist && toDoor.normalize().dot(lookDir) > 0.3) {
        best = d;
        bestDist = dist;
      }
    }
    if (best) best.target = best.target > 0.5 ? 0 : 1;
  };

  const hitsWall = (
    from: THREE.Vector3,
    direction: THREE.Vector3,
    distance: number,
  ) => {
    if (distance <= 0) return false;
    const reach = distance + playerRadius;
    if (direction.y !== 0) return castRay(from, direction, reach) !== null;
    // start above step height so stairs and kerbs are walked up, not blocked
    const lowY = from.y - eyeHeight + stepHeight;
    const headY = from.y + 0.12;
    lateral.set(-direction.z, 0, direction.x).multiplyScalar(sideSpread);
    for (let i = 0; i < bodySampleCount; i++) {
      const y = lowY + (headY - lowY) * (i / (bodySampleCount - 1));
      for (const side of [0, 1, -1]) {
        probe.set(from.x + lateral.x * side, y, from.z + lateral.z * side);
        const hit = castRay(probe, direction, reach);
        if (!hit || Math.abs(hit.face!.normal.y) >= floorNormalY) continue;
        // probe started inside a wall we brush against: its exit face must not pin us
        const leaving =
          hit.face!.normal.dot(direction) > 0 && hit.distance < playerRadius;
        if (!leaving) return true;
      }
    }
    return false;
  };

  const floorHit = (far: number) => castRay(camera.position, down, far);

  // move along one axis; when a jamb blocks it, slide sideways into the opening if a small shift frees the way
  const tryAxis = (axis: "x" | "z", amount: number) => {
    if (amount === 0) return;
    const side = axis === "x" ? "z" : "x";
    axisDir.set(0, 0, 0)[axis] = Math.sign(amount);
    origin.copy(camera.position);
    if (!hitsWall(origin, axisDir, Math.abs(amount))) {
      camera.position[axis] += amount;
      return;
    }
    for (const off of [0.08, -0.08, 0.16, -0.16, 0.24, -0.24]) {
      sideDir.set(0, 0, 0)[side] = Math.sign(off);
      if (hitsWall(camera.position, sideDir, Math.abs(off))) continue;
      nudge.copy(camera.position);
      nudge[side] += off;
      if (hitsWall(nudge, axisDir, Math.abs(amount))) continue;
      camera.position[side] += Math.sign(off) * Math.min(Math.abs(off), Math.abs(amount));
      return;
    }
  };

  useLayoutEffect(() => {
    const { bounds, groundY } = collider;
    const center = bounds.getCenter(new THREE.Vector3());
    const [x, z, lookX, lookZ] = map.spawn ?? [
      center.x,
      bounds.min.z + playerRadius + 0.8,
      center.x,
      center.z,
    ];
    // drop from above the roof line onto whatever is below the spawn point
    probe.set(x, bounds.max.y + 1, z);
    const hit = castRay(probe, down, Infinity);
    const y = (hit?.point.y ?? groundY) + eyeHeight;
    camera.position.set(x, y, z);
    camera.lookAt(lookX, y, lookZ);
    state.velocityY = 0;
    state.grounded = true;
  }, [collider, map, camera]);

  const clampToBounds = () => {
    const { bounds, groundY } = collider;
    const margin = playerRadius + 0.25;
    camera.position.x = THREE.MathUtils.clamp(
      camera.position.x,
      bounds.min.x + margin,
      bounds.max.x - margin,
    );
    camera.position.z = THREE.MathUtils.clamp(
      camera.position.z,
      bounds.min.z + margin,
      bounds.max.z - margin,
    );
    const minEyeY = groundY + eyeHeight;
    if (camera.position.y < minEyeY) {
      camera.position.y = minEyeY;
      state.velocityY = 0;
      state.grounded = true;
    }
  };

  const applyVertical = (delta: number) => {
    if (state.grounded && keys.jump) {
      state.velocityY = jumpSpeed;
      state.grounded = false;
    }
    keys.jump = false;

    if (state.grounded) {
      const hit = floorHit(eyeHeight + 0.6);
      if (!hit || hit.distance > eyeHeight + stepHeight) {
        state.grounded = false;
        return;
      }
      const targetY = hit.point.y + eyeHeight;
      // ease up onto steps instead of popping; step down instantly
      camera.position.y =
        targetY > camera.position.y
          ? THREE.MathUtils.lerp(
              camera.position.y,
              targetY,
              Math.min(1, stepUpSpeed * delta),
            )
          : targetY;
      state.velocityY = 0;
      return;
    }

    state.velocityY -= gravity * delta;
    const dy = state.velocityY * delta;
    if (dy > 0) {
      origin.copy(camera.position);
      if (hitsWall(origin, up, dy + 0.1)) state.velocityY = 0;
      else camera.position.y += dy;
      return;
    }

    const hit = floorHit(eyeHeight - dy + 0.5);
    if (hit && hit.distance <= eyeHeight) {
      camera.position.y = hit.point.y + eyeHeight;
      state.velocityY = 0;
      state.grounded = true;
      return;
    }
    camera.position.y += dy;
  };

  useFrame((_, rawDelta) => {
    const touch = touchRef.current;
    const delta = Math.min(rawDelta, 0.05);
    for (const d of doors.current) {
      if (d.t === d.target) continue;
      d.t = THREE.MathUtils.clamp(d.t + Math.sign(d.target - d.t) * doorSpeed * delta, 0, 1);
      d.obj.rotation.y = d.angle * ease(d.t);
    }
    if (!controlsRef.current?.isLocked && !touch?.enabled) return;
    if (keys.use || touch?.use) {
      keys.use = false;
      if (touch) touch.use = false;
      useDoor();
    }
    if (touch?.jump) {
      keys.jump = true;
      touch.jump = false;
    }
    const speed = keys.sprint || touch?.sprint ? sprintSpeed : walkSpeed;
    right.setFromMatrixColumn(camera.matrix, 0);
    front.crossVectors(camera.up, right);
    front.y = 0;
    front.normalize();
    right.y = 0;
    right.normalize();

    moveDir.set(0, 0, 0);
    if (keys.forward) moveDir.add(front);
    if (keys.backward) moveDir.sub(front);
    if (keys.right) moveDir.add(right);
    if (keys.left) moveDir.sub(right);
    // analog stick: magnitude scales speed, so a light push walks slowly
    let throttle = 1;
    if (touch && touch.move.lengthSq() > 0) {
      moveDir.addScaledVector(front, touch.move.y);
      moveDir.addScaledVector(right, touch.move.x);
      throttle = Math.min(touch.move.length(), 1);
    }

    if (moveDir.lengthSq() > 0) {
      moveDir.normalize().multiplyScalar(speed * throttle * delta);
      tryAxis("x", moveDir.x);
      tryAxis("z", moveDir.z);
    }

    applyVertical(delta);
    clampToBounds();
  });

  if (isTouch) return null;
  return (
    <PointerLockControls
      ref={controlsRef}
      selector="#enter"
      onLock={() => onLockChange(true)}
      onUnlock={() => onLockChange(false)}
    />
  );
}
