import { useEffect, useMemo } from "react";
import * as THREE from "three";
import { useLoader, useThree } from "@react-three/fiber";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { MeshBVH, acceleratedRaycast } from "three-mesh-bvh";
import { colliderOnly, foliage, zBias, type HouseMap } from "./maps";
import { batchStaticMeshes } from "./batch";

export type Collider = {
  mesh: THREE.Mesh;
  bounds: THREE.Box3;
  groundY: number;
  // hinged door leaves (extras.openAngle from the Blender build): animated, ray-tested on their own
  doors: THREE.Object3D[];
};

type Lamp = { x: number; z: number; top: number; radius: number };

const lampMaterial = "Lampa_LED";
// wall lamps and other fittings that glow after dusk (no extra lights: emissive only)
const glowMaterial = "Swiatlo";
const lampColor = "#ffd29a";

const isMesh = (obj: THREE.Object3D): obj is THREE.Mesh =>
  (obj as THREE.Mesh).isMesh;

const materialsOf = (mesh: THREE.Mesh) =>
  Array.isArray(mesh.material) ? mesh.material : [mesh.material];

const texturesOf = (material: THREE.Material) =>
  Object.values(material).filter(
    (v): v is THREE.Texture => (v as THREE.Texture)?.isTexture,
  );

// impostor cards ("Karta_*") are alpha-tested foliage too
const isFoliageMaterial = (name: string) => foliage.has(name) || name.startsWith("Karta_");

const isFoliage = (mesh: THREE.Mesh) =>
  materialsOf(mesh).some((m) => isFoliageMaterial(m.name));

const isDoor = (obj: THREE.Object3D) => obj.userData.openAngle !== undefined;

const inDoor = (obj: THREE.Object3D | null): boolean =>
  !!obj && (isDoor(obj) || inDoor(obj.parent));

function prepareMaterials(
  root: THREE.Object3D,
  map: HouseMap,
  anisotropy: number,
) {
  root.traverse((obj) => {
    if (!isMesh(obj)) return;
    // still part of the merged collider, which ignores visibility
    if (obj.name.startsWith(colliderOnly)) obj.visible = false;
    obj.castShadow = true;
    obj.receiveShadow = true;
    for (const material of materialsOf(obj)) {
      for (const texture of texturesOf(material)) {
        texture.anisotropy = anisotropy;
      }
      if (!map.fixMaterials) continue;
      // closed boxes: back faces only z-fight with neighbours touching the same plane
      if (!isFoliageMaterial(material.name)) material.side = THREE.FrontSide;
      if (material.name.startsWith("Karta_")) {
        // alpha-tested, not blended: sorts correctly and casts shaped shadows
        material.alphaTest = 0.5;
        material.transparent = false;
        material.depthWrite = true;
        material.side = THREE.DoubleSide;
      }
      const std = material as THREE.MeshStandardMaterial;
      // gray_* masks were authored as Non-Color in Blender; glTF forces sRGB on baseColor
      if (std.map?.name.startsWith("gray_")) {
        std.map.colorSpace = THREE.NoColorSpace;
      }
      material.needsUpdate = true;
    }
    const level = map.fixMaterials
      ? zBias.find(([prefix]) => obj.name.startsWith(prefix))?.[1]
      : undefined;
    if (!level || obj.userData.zBias) return;
    obj.userData.zBias = level;
    // materials are shared with the surface underneath, so bias a copy
    const biased = materialsOf(obj).map((m) => {
      const copy = m.clone();
      copy.polygonOffset = true;
      copy.polygonOffsetFactor = -level;
      copy.polygonOffsetUnits = -4 * level;
      return copy;
    });
    obj.material = Array.isArray(obj.material) ? biased : biased[0];
  });
}

// one merged, double-sided, BVH-indexed mesh = fast exact raycasts regardless of render side
function buildCollider(root: THREE.Object3D): Collider {
  root.updateMatrixWorld(true);
  const parts: THREE.BufferGeometry[] = [];
  const box = new THREE.Box3();
  const size = new THREE.Vector3();
  let bestArea = 0;
  let groundY = 0;
  root.traverse((obj) => {
    if (!isMesh(obj) || isFoliage(obj) || inDoor(obj)) return;
    const src = obj.geometry;
    const part = new THREE.BufferGeometry();
    // copy component-wise: positions may be interleaved
    const pos = src.getAttribute("position");
    const array = new Float32Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) {
      array[i * 3] = pos.getX(i);
      array[i * 3 + 1] = pos.getY(i);
      array[i * 3 + 2] = pos.getZ(i);
    }
    part.setAttribute("position", new THREE.BufferAttribute(array, 3));
    part.setIndex(
      src.index ? src.index.clone() : [...Array(pos.count).keys()],
    );
    part.applyMatrix4(obj.matrixWorld);
    parts.push(part);

    box.setFromObject(obj).getSize(size);
    const area = size.x * size.z;
    if (size.y <= 0.4 && area > bestArea) {
      bestArea = area;
      groundY = box.max.y;
    }
  });

  const bounds = new THREE.Box3().setFromObject(root);
  bounds.getSize(size);
  const center = bounds.getCenter(new THREE.Vector3());
  const ground = new THREE.PlaneGeometry(size.x + 2, size.z + 2);
  ground.rotateX(-Math.PI / 2);
  ground.translate(center.x, groundY, center.z);
  ground.deleteAttribute("normal");
  ground.deleteAttribute("uv");
  parts.push(ground);

  const geometry = mergeGeometries(parts);
  for (const part of parts) part.dispose();
  geometry.boundsTree = new MeshBVH(geometry);
  const mesh = new THREE.Mesh(
    geometry,
    new THREE.MeshBasicMaterial({ side: THREE.DoubleSide }),
  );
  mesh.raycast = acceleratedRaycast;
  const doors: THREE.Object3D[] = [];
  root.traverse((obj) => {
    if (isDoor(obj)) doors.push(obj);
  });
  return { mesh, bounds, groundY, doors };
}

// garden bollards are one merged mesh: split it into posts by clustering vertices in plan
function findLamps(root: THREE.Object3D): Lamp[] {
  const lamps: (Lamp & { sx: number; sz: number; n: number })[] = [];
  const v = new THREE.Vector3();
  root.traverse((obj) => {
    if (!isMesh(obj) || !materialsOf(obj).some((m) => m.name === lampMaterial))
      return;
    const pos = obj.geometry.getAttribute("position");
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(obj.matrixWorld);
      let lamp = lamps.find(
        (l) => Math.hypot(l.sx / l.n - v.x, l.sz / l.n - v.z) < 0.4,
      );
      if (!lamp) {
        lamp = { x: 0, z: 0, top: -Infinity, radius: 0, sx: 0, sz: 0, n: 0 };
        lamps.push(lamp);
      }
      lamp.sx += v.x;
      lamp.sz += v.z;
      lamp.n++;
      lamp.top = Math.max(lamp.top, v.y);
    }
    // radius pass once centres are known
    for (const lamp of lamps) {
      lamp.x = lamp.sx / lamp.n;
      lamp.z = lamp.sz / lamp.n;
    }
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(obj.matrixWorld);
      const lamp = lamps.find((l) => Math.hypot(l.x - v.x, l.z - v.z) < 0.4);
      if (lamp) lamp.radius = Math.max(lamp.radius, Math.hypot(lamp.x - v.x, lamp.z - v.z));
    }
  });
  return lamps.map(({ x, z, top, radius }) => ({ x, z, top, radius }));
}

function disposeTree(root: THREE.Object3D) {
  root.traverse((obj) => {
    if (!isMesh(obj)) return;
    obj.geometry.dispose();
    for (const material of materialsOf(obj)) {
      for (const texture of texturesOf(material)) texture.dispose();
      material.dispose();
    }
  });
}

export function House({
  map,
  night,
  onProgress,
  onReady,
}: {
  map: HouseMap;
  night: number;
  onProgress: (event: ProgressEvent) => void;
  onReady: (collider: Collider) => void;
}) {
  const gl = useThree((s) => s.gl);
  const gltf = useLoader(GLTFLoader, map.url, undefined, onProgress);
  const collider = useMemo(() => {
    prepareMaterials(gltf.scene, map, gl.capabilities.getMaxAnisotropy());
    const result = buildCollider(gltf.scene);
    for (const door of result.doors) {
      door.traverse((obj) => {
        obj.userData.noBatch = true;
      });
    }
    // one draw call per shared material; originals stay (hidden) for lamps lookup
    batchStaticMeshes(gltf.scene, gltf.scene).traverse((obj) => {
      obj.castShadow = true;
      obj.receiveShadow = true;
    });
    // batching freezes matrices; doors keep moving
    for (const door of result.doors) {
      door.traverse((obj) => {
        obj.matrixAutoUpdate = true;
      });
    }
    return result;
  }, [gltf, map, gl]);
  const lamps = useMemo(() => findLamps(gltf.scene), [gltf]);
  const glows = useMemo(() => {
    const found = new Set<THREE.MeshStandardMaterial>();
    gltf.scene.traverse((obj) => {
      if (!isMesh(obj)) return;
      for (const m of materialsOf(obj)) {
        if (m.name === glowMaterial) found.add(m as THREE.MeshStandardMaterial);
      }
    });
    return [...found];
  }, [gltf]);

  useEffect(() => {
    for (const m of glows) {
      m.emissive.set(lampColor);
      m.emissiveIntensity = 0.05 + 4 * night;
    }
  }, [glows, night]);

  useEffect(() => {
    onReady(collider);
  }, [collider, onReady]);

  useEffect(
    () => () => {
      // GPU-only dispose: StrictMode remounts re-upload transparently
      disposeTree(gltf.scene);
      collider.mesh.geometry.dispose();
      (collider.mesh.material as THREE.Material).dispose();
    },
    [gltf, collider],
  );

  return (
    <>
      <primitive object={gltf.scene} />
      {lamps.map((lamp, i) => (
        <group key={i} position={[lamp.x, lamp.top - 0.07, lamp.z]}>
          {/* glowing band just outside the post surface, so it never z-fights */}
          <mesh>
            <cylinderGeometry
              args={[lamp.radius + 0.006, lamp.radius + 0.006, 0.05, 24, 1, true]}
            />
            <meshStandardMaterial
              color="#1d1d1d"
              emissive={lampColor}
              emissiveIntensity={0.2 + 6 * night}
              toneMapped={false}
            />
          </mesh>
          {/* lights stay mounted (intensity 0 by day) so dusk does not recompile shaders */}
          <pointLight
            position={[0, 0, 0]}
            color={lampColor}
            intensity={3 * night}
            distance={6}
            decay={2}
          />
        </group>
      ))}
    </>
  );
}

// free the cached file when leaving a house, so the next visit loads fresh resources
export const forgetHouse = (map: HouseMap) =>
  useLoader.clear(GLTFLoader, map.url);
