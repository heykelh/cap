import fs from "fs";
import { feature } from "topojson-client";
import { geoContains } from "d3-geo";
// Génère lib/worldDots.ts : la carte du monde en points, à partir de Natural Earth (domaine public).
// Lancé automatiquement avant « npm run dev » et « npm run build ».
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const topo = JSON.parse(fs.readFileSync(require.resolve("world-atlas/land-50m.json"), "utf8"));
const land = feature(topo, topo.objects.land);
// Projection équirectangulaire, latitudes 75N à 56S, 1 unité = 1 degré
const STEP = 1.5, LAT_TOP = 75, LAT_BOTTOM = -56;
let d = ""; let n = 0;
for (let lat = LAT_TOP; lat >= LAT_BOTTOM; lat -= STEP) {
  for (let lon = -180; lon < 180; lon += STEP) {
    if (geoContains(land, [lon + STEP / 2, lat - STEP / 2])) {
      const x = (lon + 180).toFixed(1), y = (LAT_TOP - lat).toFixed(1);
      d += `M${x} ${y}h.9v.9h-.9z`; n++;
    }
  }
}
const W = 360, H = LAT_TOP - LAT_BOTTOM;
fs.writeFileSync(new URL("../lib/worldDots.ts", import.meta.url),
`// Carte du monde en points, générée depuis Natural Earth (domaine public) via world-atlas.
// Projection équirectangulaire : x = longitude + 180, y = ${LAT_TOP} - latitude.
export const MAP = { width: ${W}, height: ${H}, latTop: ${LAT_TOP} } as const;
export const WORLD_DOTS = "${d}";
`);
console.log(`Carte générée : ${n} points`);
