// Géométrie de la carte : projection équirectangulaire et arcs de grand cercle.
import { MAP } from "./worldDots";

export const CDG = { lat: 49.0097, lon: 2.5479 };

// Coordonnées de secours si l'export ne les fournit pas (aéroports, valeurs arrondies).
const FALLBACK: Record<string, [number, number]> = {
  CLT: [35.214, -80.943], MCO: [28.429, -81.309], DPS: [-8.748, 115.167], ALA: [43.352, 77.04],
  CCS: [10.601, -66.991], SSA: [-12.909, -38.322], DEN: [39.856, -104.674], CUR: [12.189, -68.96],
  CGK: [-6.126, 106.656], ACC: [5.605, -0.167], KGL: [-1.968, 30.139], SDQ: [18.43, -69.669],
  MNL: [14.509, 121.02], MDE: [6.165, -75.423], KUL: [2.746, 101.71], IKA: [35.416, 51.152],
  UBN: [47.646, 106.819], ASB: [37.987, 58.361], UIO: [-0.129, -78.358], LAS: [36.084, -115.154],
};

export function coords(iata: string, lat?: number | null, lon?: number | null): [number, number] | null {
  if (lat != null && lon != null) return [lat, lon];
  return FALLBACK[iata] ?? null;
}

export function project(lat: number, lon: number): [number, number] {
  return [lon + 180, MAP.latTop - lat];
}

const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

// Arc de grand cercle entre deux points, sous forme de chemin SVG.
export function arcPath(from: { lat: number; lon: number }, to: { lat: number; lon: number }, steps = 64) {
  const φ1 = rad(from.lat), λ1 = rad(from.lon), φ2 = rad(to.lat), λ2 = rad(to.lon);
  const d = 2 * Math.asin(Math.sqrt(Math.sin((φ2 - φ1) / 2) ** 2 +
    Math.cos(φ1) * Math.cos(φ2) * Math.sin((λ2 - λ1) / 2) ** 2));
  const pts: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const f = i / steps;
    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(φ1) * Math.cos(λ1) + B * Math.cos(φ2) * Math.cos(λ2);
    const y = A * Math.cos(φ1) * Math.sin(λ1) + B * Math.cos(φ2) * Math.sin(λ2);
    const z = A * Math.sin(φ1) + B * Math.sin(φ2);
    pts.push(project(deg(Math.atan2(z, Math.sqrt(x * x + y * y))), deg(Math.atan2(y, x))));
  }
  return pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`).join("");
}
