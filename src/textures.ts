import * as THREE from "three";

/**
 * Procedural PBR textures (albedo + normal + roughness) that replace the
 * flat placeholder images embedded in the GLB. Every pattern is tileable,
 * generated once per material at load, and sized for the device.
 */

type Sample = {
  /** Albedo multiplier around 1 applied to the material's base colour. */
  tone: number;
  /** Per-channel tint offsets (small, around 0). */
  tint?: [number, number, number];
  /** Height 0..1 used to derive the normal map. */
  height: number;
  /** Roughness multiplier around 1. */
  rough: number;
};

type Pattern = (u: number, v: number, out: Sample) => void;

type Recipe = {
  pattern: (seed: number) => Pattern;
  /** Normal map strength. */
  bump: number;
  /** Repeat applied when the GLB material has no texture transform. */
  repeat?: number;
};

// ---------------------------------------------------------------------------
// Tileable noise

const hash = (x: number, y: number, seed: number) => {
  let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(seed, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
};

const mod = (a: number, n: number) => ((a % n) + n) % n;
const smooth = (t: number) => t * t * (3 - 2 * t);
const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);

/** Value noise on [0,1)^2, periodic with `px` × `py` cells. Returns 0..1. */
const noise = (u: number, v: number, px: number, py: number, seed: number) => {
  const x = u * px;
  const y = v * py;
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const fx = smooth(x - xi);
  const fy = smooth(y - yi);
  const x0 = mod(xi, px);
  const y0 = mod(yi, py);
  const x1 = mod(xi + 1, px);
  const y1 = mod(yi + 1, py);
  const a = hash(x0, y0, seed);
  const b = hash(x1, y0, seed);
  const c = hash(x0, y1, seed);
  const d = hash(x1, y1, seed);
  return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
};

/** Fractal noise, periodic on the unit square. Returns roughly 0..1. */
const fbm = (
  u: number,
  v: number,
  px: number,
  py: number,
  octaves: number,
  seed: number,
) => {
  let sum = 0;
  let amp = 0.5;
  let norm = 0;
  for (let o = 0; o < octaves; o++) {
    sum += amp * noise(u, v, px, py, seed + o * 17);
    norm += amp;
    amp *= 0.5;
    px *= 2;
    py *= 2;
  }
  return sum / norm;
};

// ---------------------------------------------------------------------------
// Patterns

type WoodOptions = {
  /** Board rows per tile across v (0 = solid timber, no seams). */
  planks: number;
  /** Board end joints per row along u. */
  joints: number;
  /** Grain lines per board. */
  grain: number;
  /** Per-board tone variation. */
  variation: number;
};

const wood =
  ({ planks, joints, grain, variation }: WoodOptions) =>
  (seed: number): Pattern => {
    const rows = Math.max(planks, 1);
    const lines = Math.round(grain * rows);
    return (u, v, out) => {
      const row = Math.min(Math.floor(v * rows), rows - 1);
      const local = v * rows - row;
      let board = row;
      let seam = 1;
      if (planks > 0) {
        seam = Math.min(smooth(clamp01(local / 0.03)), smooth(clamp01((1 - local) / 0.03)));
        if (joints > 0) {
          const shift = hash(row, 7, seed);
          const along = mod(u * joints + shift, 1);
          const col = Math.floor(mod(u * joints + shift, joints));
          board = row * 31 + col;
          const edge = Math.min(along, 1 - along) * (1 / joints) * rows;
          seam = Math.min(seam, smooth(clamp01(edge / 0.03)));
        }
      }
      const warp = fbm(u, v, 3, 2 * rows, 3, seed + 5);
      const ring = Math.sin(2 * Math.PI * (v * lines + warp * 2.5));
      const fine = noise(u, v, 4, lines * 6, seed + 9);
      const knot = fbm(u, v, 6, 3 * rows, 2, seed + 13);
      const bt = (hash(board, 3, seed) - 0.5) * 2 * variation;
      const grainTone = 0.92 + 0.1 * ring * ring - 0.08 * fine + (knot > 0.72 ? -0.18 * (knot - 0.72) / 0.28 : 0);
      out.tone = (1 + bt) * grainTone * (0.55 + 0.45 * seam);
      out.tint = [bt * 0.15, 0, -bt * 0.1];
      out.height = 0.4 * seam + 0.06 * ring + 0.04 * fine;
      out.rough = (0.92 + 0.12 * fine) * (seam < 0.5 ? 1.15 : 1);
    };
  };

type BondOptions = {
  rows: number;
  cols: number;
  /** Row offset as a fraction of a cell (0.5 = running bond); <0 = random. */
  stagger: number;
  /** Joint width as a fraction of a cell. */
  gap: number;
  /** Bevel width as a fraction of a cell. */
  bevel: number;
  variation: number;
  /** Tone of the joint relative to the cells. */
  groutTone: number;
  /** Surface noise amount on each cell. */
  grit: number;
  /** Darken toward the bottom of each cell (overlapping roof tiles). */
  lap?: number;
};

const bond =
  (o: BondOptions) =>
  (seed: number): Pattern => {
    return (u, v, out) => {
      const y = v * o.rows;
      const row = Math.min(Math.floor(y), o.rows - 1);
      const fy = y - row;
      const shift =
        o.stagger < 0 ? hash(row, 1, seed) : mod(row * o.stagger, 1);
      const x = mod(u * o.cols + shift, o.cols);
      const col = Math.floor(x);
      const fx = x - col;
      const cell = hash(col, row, seed);
      const ex = Math.min(fx, 1 - fx) * (o.rows / o.cols);
      const ey = Math.min(fy, 1 - fy);
      const edge = Math.min(ex, ey);
      const inGap = edge < o.gap * 0.5;
      const bevel = smooth(clamp01((edge - o.gap * 0.5) / o.bevel));
      const grit = fbm(u, v, 8 * o.cols, 8 * o.rows, 4, seed + 3);
      const blotch = fbm(u, v, 4, 4, 3, seed + 7);
      const lap = o.lap ? 1 - o.lap * fy : 1;
      const ct = (cell - 0.5) * 2 * o.variation;
      if (inGap) {
        out.tone = o.groutTone * (0.95 + 0.1 * grit);
        out.tint = [0, 0, 0];
        out.height = 0.05 * grit;
        out.rough = 1.1;
        return;
      }
      out.tone =
        (1 + ct) * (0.94 + 0.1 * blotch) * (1 - o.grit * (grit - 0.5)) * lap * (0.85 + 0.15 * bevel);
      const t = (hash(col, row, seed + 2) - 0.5) * o.variation;
      out.tint = [t * 0.4, t * 0.15, -t * 0.3];
      out.height = 0.35 + 0.5 * bevel + o.grit * 0.5 * grit + (o.lap ? 0.2 * (1 - fy) : 0);
      out.rough = 0.95 + 0.1 * grit - 0.05 * bevel;
    };
  };

const stucco =
  (scale: number, depth: number) =>
  (seed: number): Pattern =>
  (u, v, out) => {
    const fine = fbm(u, v, 16 * scale, 16 * scale, 4, seed);
    const coarse = fbm(u, v, 2, 2, 3, seed + 11);
    out.tone = 0.96 + 0.07 * (coarse - 0.5) + depth * 0.12 * (fine - 0.5);
    out.tint = [0, 0, 0];
    out.height = fine;
    out.rough = 0.95 + 0.1 * fine;
  };

const grass = (seed: number): Pattern => (u, v, out) => {
  const patch = fbm(u, v, 3, 3, 4, seed);
  const blades = noise(u, v, 96, 24, seed + 4) * 0.5 + noise(u, v, 24, 96, seed + 8) * 0.5;
  const speck = noise(u, v, 128, 128, seed + 12);
  const dry = clamp01((patch - 0.62) * 2) * 0.5;
  out.tone = 0.78 + 0.35 * blades + 0.12 * (speck - 0.5) - 0.1 * dry;
  out.tint = [0.12 * dry, 0.04 * dry - 0.03 * (blades - 0.5), -0.05 * dry];
  out.height = 0.6 * blades + 0.4 * speck;
  out.rough = 1;
};

const fabric =
  (threads: number) =>
  (seed: number): Pattern =>
  (u, v, out) => {
    const wu = Math.sin(2 * Math.PI * u * threads);
    const wv = Math.sin(2 * Math.PI * v * threads);
    const over = wu * wv > 0 ? Math.abs(wu) : Math.abs(wv);
    const slub = fbm(u, v, threads / 4, 4, 2, seed);
    out.tone = 0.86 + 0.14 * over + 0.1 * (slub - 0.5);
    out.tint = [0, 0, 0];
    out.height = 0.6 * over + 0.4 * slub;
    out.rough = 1;
  };

const fibre = (seed: number): Pattern => (u, v, out) => {
  const n = fbm(u, v, 64, 64, 3, seed);
  const tuft = fbm(u, v, 8, 8, 2, seed + 5);
  out.tone = 0.85 + 0.25 * n + 0.1 * (tuft - 0.5);
  out.tint = [0, 0, 0];
  out.height = n;
  out.rough = 1;
};

const marble = (seed: number): Pattern => (u, v, out) => {
  const warp = fbm(u, v, 3, 3, 5, seed);
  const vein = Math.abs(Math.sin(2 * Math.PI * (u + v * 2 + warp * 2.2)));
  const fine = Math.abs(Math.sin(2 * Math.PI * (u * 3 - v + fbm(u, v, 6, 6, 4, seed + 3) * 3)));
  const dark = (1 - smooth(clamp01(vein * 6))) * 0.35 + (1 - smooth(clamp01(fine * 10))) * 0.15;
  out.tone = 1.04 - dark + 0.04 * (warp - 0.5);
  out.tint = [0, 0, dark * 0.02];
  out.height = 0.5;
  out.rough = 1 + dark * 0.6;
};

const recipes: Record<string, Recipe> = {
  terrace_decking: {
    pattern: wood({ planks: 2, joints: 1, grain: 6, variation: 0.12 }),
    bump: 1.2,
  },
  oak_parquet: {
    pattern: wood({ planks: 6, joints: 1, grain: 5, variation: 0.1 }),
    bump: 0.6,
  },
  cedral_dark_oak: {
    pattern: wood({ planks: 1, joints: 0, grain: 7, variation: 0.06 }),
    bump: 1.4,
  },
  cedral_natural_oak: {
    pattern: wood({ planks: 1, joints: 0, grain: 7, variation: 0.06 }),
    bump: 1.4,
  },
  oak_dark: { pattern: wood({ planks: 0, joints: 0, grain: 9, variation: 0 }), bump: 0.4 },
  oak_natural: { pattern: wood({ planks: 0, joints: 0, grain: 9, variation: 0 }), bump: 0.4 },
  walnut: { pattern: wood({ planks: 0, joints: 0, grain: 12, variation: 0 }), bump: 0.3 },
  bark: { pattern: wood({ planks: 0, joints: 0, grain: 4, variation: 0 }), bump: 2.5 },
  kostka_brukowa: {
    pattern: bond({ rows: 8, cols: 4, stagger: 0.5, gap: 0.08, bevel: 0.12, variation: 0.14, groutTone: 0.55, grit: 0.25 }),
    bump: 2,
  },
  concrete_paving: {
    pattern: bond({ rows: 1, cols: 1, stagger: 0, gap: 0.02, bevel: 0.03, variation: 0.05, groutTone: 0.6, grit: 0.3 }),
    bump: 1.2,
  },
  sandstone_cladding: {
    pattern: bond({ rows: 8, cols: 4, stagger: -1, gap: 0.07, bevel: 0.1, variation: 0.16, groutTone: 0.75, grit: 0.35 }),
    bump: 2.2,
  },
  gres_floor: {
    pattern: bond({ rows: 1, cols: 1, stagger: 0, gap: 0.012, bevel: 0.01, variation: 0.03, groutTone: 0.8, grit: 0.08 }),
    bump: 0.6,
  },
  terakota_floor: {
    pattern: bond({ rows: 1, cols: 1, stagger: 0, gap: 0.03, bevel: 0.03, variation: 0.08, groutTone: 0.85, grit: 0.12 }),
    bump: 0.8,
  },
  roof_tile_anthracite: {
    pattern: bond({ rows: 3, cols: 2, stagger: 0.5, gap: 0.03, bevel: 0.05, variation: 0.08, groutTone: 0.45, grit: 0.15, lap: 0.35 }),
    bump: 2.5,
  },
  render_grey: { pattern: stucco(1, 1), bump: 1.2 },
  plaster_interior: { pattern: stucco(2, 0.4), bump: 0.4 },
  lawn: { pattern: grass, bump: 1.5 },
  linen_upholstery: { pattern: fabric(48), bump: 0.8 },
  wool_charcoal: { pattern: fibre, bump: 1.2, repeat: 4 },
  marble_worktop: { pattern: marble, bump: 0.05, repeat: 1 },
};

// ---------------------------------------------------------------------------
// Baking

const seedOf = (name: string) => {
  let h = 2166136261;
  for (let i = 0; i < name.length; i++) h = Math.imul(h ^ name.charCodeAt(i), 16777619);
  return h >>> 0;
};

const makeTexture = (data: Uint8Array, size: number, srgb: boolean) => {
  const texture = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  texture.needsUpdate = true;
  return texture;
};

type Baked = { map: THREE.Texture; normalMap: THREE.Texture; roughnessMap: THREE.Texture };

const bake = (
  recipe: Recipe,
  seed: number,
  base: THREE.Color,
  baseRoughness: number,
  size: number,
): Baked => {
  const pattern = recipe.pattern(seed);
  const n = size * size;
  const height = new Float32Array(n);
  const albedo = new Uint8Array(n * 4);
  const rough = new Uint8Array(n * 4);
  const s: Sample = { tone: 1, height: 0, rough: 1 };
  const rgb = { r: 0, g: 0, b: 0 };
  base.getRGB(rgb, THREE.SRGBColorSpace);

  for (let y = 0; y < size; y++) {
    const v = (y + 0.5) / size;
    for (let x = 0; x < size; x++) {
      const i = y * size + x;
      s.tint = undefined;
      pattern((x + 0.5) / size, v, s);
      const t = s.tint;
      albedo[i * 4] = 255 * clamp01(rgb.r * s.tone + (t ? t[0] : 0));
      albedo[i * 4 + 1] = 255 * clamp01(rgb.g * s.tone + (t ? t[1] : 0));
      albedo[i * 4 + 2] = 255 * clamp01(rgb.b * s.tone + (t ? t[2] : 0));
      albedo[i * 4 + 3] = 255;
      rough[i * 4 + 1] = 255 * clamp01(baseRoughness * s.rough);
      rough[i * 4 + 3] = 255;
      height[i] = s.height;
    }
  }

  // Central differences in tangent space (+v = +y, no glTF flip since the
  // data is uploaded unflipped); strength scales with resolution so the bump
  // reads the same at every texture size.
  const normal = new Uint8Array(n * 4);
  const k = recipe.bump * (size / 256);
  for (let y = 0; y < size; y++) {
    const up = ((y + size - 1) % size) * size;
    const dn = ((y + 1) % size) * size;
    const row = y * size;
    for (let x = 0; x < size; x++) {
      const l = (x + size - 1) % size;
      const r = (x + 1) % size;
      const dx = (height[row + r] - height[row + l]) * k;
      const dy = (height[dn + x] - height[up + x]) * k;
      const inv = 1 / Math.sqrt(dx * dx + dy * dy + 1);
      const i = (row + x) * 4;
      normal[i] = 255 * (0.5 - 0.5 * dx * inv);
      normal[i + 1] = 255 * (0.5 - 0.5 * dy * inv);
      normal[i + 2] = 255 * (0.5 + 0.5 * inv);
      normal[i + 3] = 255;
    }
  }

  return {
    map: makeTexture(albedo, size, true),
    normalMap: makeTexture(normal, size, false),
    roughnessMap: makeTexture(rough, size, false),
  };
};

const applyTransform = (target: THREE.Texture, source: THREE.Texture | null, repeat: number) => {
  if (source) {
    target.repeat.copy(source.repeat);
    target.offset.copy(source.offset);
    target.rotation = source.rotation;
    target.center.copy(source.center);
  } else {
    target.repeat.set(repeat, repeat);
  }
};

const yieldToBrowser = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

/**
 * Replace the GLB's placeholder textures with baked procedural PBR maps.
 * Yields between materials so the page stays responsive while baking.
 */
export const upgradeMaterials = async (
  root: THREE.Object3D,
  options: { size: number; anisotropy: number },
) => {
  const materials = new Map<string, THREE.MeshStandardMaterial>();
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh) return;
    const list = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const m of list) {
      if ((m as THREE.MeshStandardMaterial).isMeshStandardMaterial) {
        materials.set(m.uuid, m as THREE.MeshStandardMaterial);
      }
    }
  });

  for (const material of materials.values()) {
    const recipe = recipes[material.name];
    if (!recipe) continue;
    const old = material.map;
    const baked = bake(recipe, seedOf(material.name), material.color, material.roughness, options.size);
    for (const tex of [baked.map, baked.normalMap, baked.roughnessMap]) {
      applyTransform(tex, old, recipe.repeat ?? 1);
      tex.anisotropy = options.anisotropy;
    }
    const disposed = new Set([material.map, material.roughnessMap, material.metalnessMap]);
    for (const tex of disposed) tex?.dispose();
    material.map = baked.map;
    material.normalMap = baked.normalMap;
    material.normalScale.set(1, 1);
    material.roughnessMap = baked.roughnessMap;
    material.metalnessMap = null;
    material.color.set(0xffffff);
    material.roughness = 1;
    material.needsUpdate = true;
    await yieldToBrowser();
  }
};
