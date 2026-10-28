import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

const ATTRIBUTES = ["position", "normal", "uv"] as const;

/**
 * Bake a mesh's world transform into a standalone indexed geometry with only
 * the attributes every batch shares.
 */
const toWorld = (mesh: THREE.Mesh) => {
  const source = mesh.geometry;
  const geometry = new THREE.BufferGeometry();
  for (const name of ATTRIBUTES) {
    // component-wise copy: glTF attributes may be interleaved, and cloning those logs per call
    const attr = source.getAttribute(name);
    const array = new Float32Array(attr.count * attr.itemSize);
    for (let i = 0; i < attr.count; i++) {
      for (let k = 0; k < attr.itemSize; k++) {
        array[i * attr.itemSize + k] = attr.getComponent(i, k);
      }
    }
    geometry.setAttribute(name, new THREE.BufferAttribute(array, attr.itemSize));
  }
  const count = source.getAttribute("position").count;
  const index = source.index
    ? Array.from(source.index.array)
    : Array.from({ length: count }, (_, i) => i);
  // Mirrored transforms flip winding; restore it so back-face culling holds.
  if (mesh.matrixWorld.determinant() < 0) {
    for (let i = 0; i < index.length; i += 3) {
      const t = index[i + 1];
      index[i + 1] = index[i + 2];
      index[i + 2] = t;
    }
  }
  geometry.setIndex(index);
  geometry.applyMatrix4(mesh.matrixWorld);
  return geometry;
};

/**
 * Merge every static opaque mesh that shares a material into one draw call.
 * The original meshes stay in the scene, hidden, so raycast-based collision
 * keeps its per-object bounding-sphere culling.
 */
export const batchStaticMeshes = (root: THREE.Object3D, parent: THREE.Object3D) => {
  root.updateMatrixWorld(true);
  const groups = new Map<THREE.Material, THREE.Mesh[]>();
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh || !mesh.visible || Array.isArray(mesh.material)) return;
    // vertex colours are not carried into the batch: leave those meshes alone
    if (mesh.geometry.getAttribute("color")) return;
    if (mesh.userData.noBatch) return;
    if (mesh.material.transparent) return;
    if (!ATTRIBUTES.every((name) => mesh.geometry.getAttribute(name))) return;
    const list = groups.get(mesh.material) ?? [];
    list.push(mesh);
    groups.set(mesh.material, list);
  });

  const batches = new THREE.Group();
  batches.name = "batches";
  for (const [material, meshes] of groups) {
    if (meshes.length < 2) continue;
    const geometries = meshes.map(toWorld);
    const merged = mergeGeometries(geometries, false);
    for (const g of geometries) g.dispose();
    if (!merged) continue;
    merged.computeBoundingSphere();
    const batch = new THREE.Mesh(merged, material);
    batch.name = `batch_${material.name}`;
    batch.matrixAutoUpdate = false;
    batches.add(batch);
    for (const mesh of meshes) mesh.visible = false;
  }
  parent.add(batches);

  root.traverse((obj) => {
    obj.matrixAutoUpdate = false;
  });
  return batches;
};
