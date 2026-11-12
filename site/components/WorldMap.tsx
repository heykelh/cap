// Carte du monde animée : arcs de grand cercle entre Paris CDG et les destinations du radar.
// Entièrement en SVG et CSS : aucune vidéo à charger, et l'animation s'arrête si l'utilisateur
// a demandé à réduire les animations.
import { MAP, WORLD_DOTS } from "@/lib/worldDots";
import { CDG, arcPath, coords, project } from "@/lib/geo";
import type { RadarRow } from "@/lib/data";

type Props = { rows: RadarRow[]; light?: boolean; labels?: number; title: string };

export function WorldMap({ rows, light = false, labels = 6, title }: Props) {
  const [cx, cy] = project(CDG.lat, CDG.lon);
  const dests = rows
    .map((r) => ({ r, c: coords(r.iata, r.lat, r.lon) }))
    .filter((d): d is { r: RadarRow; c: [number, number] } => d.c !== null);
  const flown = dests[0];

  return (
    <svg
      className={`map${light ? " light" : ""}`}
      viewBox={`0 0 ${MAP.width} ${MAP.height}`}
      role="img"
      aria-label={title}
    >
      <path className="land" d={WORLD_DOTS} />
      {dests.map(({ r, c }, i) => (
        <path
          key={`arc-${r.iata}`}
          id={`arc-${r.iata}`}
          className="arc"
          d={arcPath(CDG, { lat: c[0], lon: c[1] })}
          style={{ animationDelay: `${0.15 * i}s` }}
        />
      ))}
      {dests.map(({ r, c }, i) => {
        const [x, y] = project(c[0], c[1]);
        return (
          <g key={`pt-${r.iata}`}>
            <circle className="pulse" cx={x} cy={y} r="1.6" style={{ animationDelay: `${0.2 * i}s` }} />
            <circle className="dest" cx={x} cy={y} r="0.9" />
            {i < labels && (
              <text className="label" x={x + 1.8} y={y + 1.1}>
                {r.ville ?? r.iata}
              </text>
            )}
          </g>
        );
      })}
      {flown && (
        <path
          className="plane"
          d="M-1.6 0 L1.6 0 M0.2 -1.3 L0.9 0 L0.2 1.3 M-1.3 -0.6 L-1.6 0 L-1.3 0.6"
          stroke={light ? "#11295a" : "#ffffff"}
          strokeWidth="0.45"
          strokeLinecap="round"
          style={{ offsetPath: `path("${arcPath(CDG, { lat: flown.c[0], lon: flown.c[1] })}")` }}
        />
      )}
      <circle className="hub" cx={cx} cy={cy} r="1.5" />
      <text className="label" x={cx - 13} y={cy - 2.4} style={{ fontWeight: 700 }}>
        Paris CDG
      </text>
    </svg>
  );
}
