export type HouseMap = {
  id: string;
  name: string;
  meta: string;
  url: string;
  thumb?: string;
  // Blender-built models: everything exported double-sided, gray_* masks baked in linear space
  fixMaterials: boolean;
  // [x, z, lookX, lookZ] in model space; default is in front of the bounds
  spawn?: [number, number, number, number];
};

const base = import.meta.env.BASE_URL;

export const maps: HouseMap[] = [
  {
    id: "wojtek",
    name: "Dom Wojtek",
    meta: "Ogród zimowy, wiata, szczyt z przeszkleniem",
    url: `${base}models/wojtek.glb`,
    thumb: `${base}models/wojtek.jpg`,
    fixMaterials: true,
    spawn: [8.4, 5, 8.4, 0],
  },
  {
    id: "hanka",
    name: "Hanka 3",
    meta: "Dom parterowy z wyposażeniem",
    url: `${base}models/hanka.glb`,
    fixMaterials: false,
  },
];

// foliage: no collisions, stays double-sided (cards / open cones)
export const foliage = new Set([
  "Trawa_ozdobna",
  "Lawenda",
  "Hortensja",
  "Liscie_krzew",
  "Liscie",
  "Igliwie",
]);

// meshes built flush with another surface (plinth on wall, edging in path, floor in door cut-outs…):
// depth bias by name prefix, higher level wins where faces are coplanar
export const zBias: [string, number][] = [
  ["Plyta_parter", 1],
  ["Cokol_", 1],
  ["Szczyt_deski_", 1],
  ["Szczyt_listwy_", 2],
  ["Parapet_", 1],
  ["Okiennice_", 1],
  ["Akcent_deski_", 1],
  ["Sciana_wew_", 1],
  ["Sciana_S_wypelnienie", 1],
  ["Sciana_N_wypelnienie", 1],
  ["Krokwie_A", 1],
  ["Podbitka_A", 1],
  ["Schody", 1],
  ["Strop", 1],
  ["Okno_dachowe_kolnierz_", 1],
  ["Okno_dachowe_A", 2],
  ["Okno_rama_", 2],
  ["Drzwi_", 2],
  ["Taras_", 1],
  ["Weranda", 1],
  ["Obrzeza", 2],
  ["Oranzeria_posadzka", 3],
  ["Przepust_podsypka", 1],
  ["Kocie_lby", 2],
  ["Stopnie_A", 2],
];
