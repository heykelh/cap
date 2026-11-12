"use client";
// Étude de marché à la demande : n'importe quelle destination, desservie par Paris ou non.
// Interroge d'abord l'API Cloud Run (BigQuery en direct), puis bascule sur l'export si besoin.
import { useEffect, useMemo, useRef, useState } from "react";
import type { Requete } from "@/lib/data";
import { Simulator } from "./Simulator";
import { QueryBlock, bytes } from "./QueryBlock";
import { fileKey } from "@/lib/files";

type Origin = {
  icao: string; iata: string; ville: string | null; paris: boolean; pax_l12: number; pax_p12: number;
  vols_l12: number; remplissage: number | null; croissance: number | null; mois_masques: number;
  donnees_jusqu_a: string | null; reguliere: boolean;
};
type Study = {
  iata: string; aeroport: string | null; ville: string; pays: string | null; distance_km: number | null;
  statut: "desservie" | "opportunite" | "non_desservie"; trafic_total_l12: number; croissance: number | null;
  paris: { pax_l12: number; part: number | null; rang: number | null; masque: boolean; aeroports: string[] };
  origines: Origin[]; mensuel: { mois: string; paris: number; hubs: number; paris_masque: boolean }[];
  opportunite: { opportunity_score: number; segment: string } | null;
  sante: { alert: string; lf_l12: number | null; lf_delta_pts: number | null; growth_pax: number | null } | null;
  lecture: string[]; scenario: { freq: number; aircraft: string }; dossier: boolean | null;
  source?: string; requetes?: Requete[];
};
type IndexRow = { iata: string; ville: string | null; aeroport: string | null; pays: string | null; statut: string; pax: number; dossier: boolean };

type Props = {
  api: string;
  hypotheses: {
    yield: number; cask: number; fuel: number; loadFactor: number; weeks: number;
    aircraft: Record<string, { seats: number }>;
  };
};

const nf = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const pct = (x: number | null | undefined, d = 1) => (x == null ? "n.d." : `${(x * 100).toFixed(d).replace(".", ",")} %`);
const spct = (x: number | null | undefined) => (x == null ? "n.d." : `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1).replace(".", ",")} %`);
const STATUS = {
  desservie: { label: "Desservie depuis Paris", tone: "go" },
  opportunite: { label: "Opportunité au radar", tone: "watch" },
  non_desservie: { label: "Non desservie, hors radar", tone: "stop" },
} as const;
const HEALTH: Record<string, string> = {
  ras: "Aucun signal d'alerte", trafic_en_baisse: "Trafic en baisse", remplissage_en_baisse: "Remplissage en baisse",
  remplissage_faible: "Remplissage faible", capacite_en_avance_sur_demande: "Capacité en avance sur la demande",
  donnees_masquees: "Volumes masqués par Eurostat",
};

function Chart({ data }: { data: Study["mensuel"] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (data.length < 2) return <p className="muted-d">Pas assez de mois publiés pour tracer l'évolution.</p>;
  const W = 760, H = 260, L = 56, R = 14, T = 16, B = 30;
  const max = Math.max(1, ...data.map((d) => Math.max(d.paris, d.hubs)));
  const x = (i: number) => L + (i / (data.length - 1)) * (W - L - R);
  const y = (v: number) => T + (1 - v / max) * (H - T - B);
  const path = (k: "paris" | "hubs") => data.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(d[k]).toFixed(1)}`).join("");
  const area = `${path("hubs")}L${x(data.length - 1)} ${H - B}L${x(0)} ${H - B}Z`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const years = data.map((d, i) => ({ i, y: d.mois.slice(0, 4), m: d.mois.slice(5) })).filter((d) => d.m === "01");
  const h = hover != null ? data[hover] : null;
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img"
        aria-label="Passagers par mois depuis Paris et depuis les 16 hubs européens"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          setHover(Math.max(0, Math.min(data.length - 1, Math.round(((px - L) / (W - L - R)) * (data.length - 1)))));
        }}>
        <defs>
          <linearGradient id="hubfill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#8fbbe9" stopOpacity=".28" />
            <stop offset="1" stopColor="#8fbbe9" stopOpacity="0" />
          </linearGradient>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="grid-line" />
            <text x={L - 8} y={y(t) + 4} className="axis" textAnchor="end">{t >= 1e6 ? `${(t / 1e6).toFixed(1).replace(".", ",")} M` : `${nf.format(t / 1e3)} k`}</text>
          </g>
        ))}
        {years.map((d) => (
          <text key={d.y} x={x(d.i)} y={H - 8} className="axis" textAnchor="middle">{d.y}</text>
        ))}
        <path d={area} fill="url(#hubfill)" />
        <path d={path("hubs")} className="line hubs" />
        <path d={path("paris")} className="line paris" />
        {h && hover != null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} className="cursor" />
            <circle cx={x(hover)} cy={y(h.hubs)} r="4" className="dot hubs" />
            <circle cx={x(hover)} cy={y(h.paris)} r="4" className="dot paris" />
          </g>
        )}
      </svg>
      <div className="legend">
        <span><i className="lg paris" /> Paris (CDG et Orly)</span>
        <span><i className="lg hubs" /> 16 hubs européens</span>
        {h && <span className="hover-val">{h.mois} · Paris {nf.format(h.paris)}{h.paris_masque ? " (masqué)" : ""} · hubs {nf.format(h.hubs)}</span>}
      </div>
    </div>
  );
}

export function MarketStudy({ api, hypotheses }: Props) {
  const [index, setIndex] = useState<IndexRow[]>([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [study, setStudy] = useState<Study | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [mode, setMode] = useState<"live" | "export" | null>(null);
  const [message, setMessage] = useState("");
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [showQueries, setShowQueries] = useState(false);
  const reqId = useRef(0);

  useEffect(() => {
    fetch("/marche/index.json").then((r) => r.json()).then((d) => setIndex(d.destinations ?? [])).catch(() => setIndex([]));
    const d = new URLSearchParams(window.location.search).get("d");
    if (d) load(d);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const suggestions = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    return index
      .filter((r) => r.iata.toLowerCase().startsWith(s) || (r.ville ?? "").toLowerCase().includes(s) || (r.aeroport ?? "").toLowerCase().includes(s))
      .slice(0, 8);
  }, [q, index]);

  const examples = useMemo(() => {
    const served = index.filter((r) => r.statut === "desservie").slice(0, 3);
    const opp = index.filter((r) => r.statut === "opportunite").slice(0, 3);
    return [...served, ...opp];
  }, [index]);

  async function load(raw: string) {
    const iata = raw.trim().toUpperCase().slice(0, 3);
    if (!/^[A-Z]{3}$/.test(iata)) return;
    const my = ++reqId.current;
    setOpen(false);
    setQ("");
    setState("loading");
    setShowQueries(false);
    window.history.replaceState(null, "", `?d=${iata}`);
    const t0 = performance.now();
    if (api) {
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 12000);
        const res = await fetch(`${api}/marche/${iata}`, { signal: ctrl.signal });
        clearTimeout(timer);
        if (res.ok) {
          const data = await res.json();
          if (my !== reqId.current) return;
          setStudy(data); setMode("live"); setElapsed(performance.now() - t0); setState("ok");
          return;
        }
        if (res.status === 404) {
          if (my !== reqId.current) return;
          setState("error"); setMessage(`Aucune donnée pour ${iata} : ni Paris ni les 16 hubs n'y volent, ou le code est inconnu.`);
          return;
        }
      } catch { /* API injoignable : on passe à l'export */ }
    }
    try {
      const res = await fetch(`/marche/${fileKey(iata)}.json`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      if (my !== reqId.current) return;
      setStudy(data); setMode("export"); setElapsed(null); setState("ok");
    } catch {
      if (my !== reqId.current) return;
      setState("error");
      setMessage(`${iata} ne figure pas dans l'export (trafic trop faible ou code inconnu)${api ? " et l'API ne répond pas" : ""}.`);
    }
  }

  const s = study;
  const st = s ? STATUS[s.statut] : null;
  const maxPax = s ? Math.max(1, ...s.origines.map((o) => o.pax_l12)) : 1;
  const bytesRead = s?.requetes?.reduce((a, r) => a + (r.octets_lus || 0), 0) ?? 0;

  return (
    <div className="market">
      <form className="search" role="search" onSubmit={(e) => { e.preventDefault(); load(suggestions[0]?.iata ?? q); }}>
        <label htmlFor="dest-search" className="sr-only">Destination</label>
        <input id="dest-search" value={q} autoComplete="off" placeholder="Une ville ou un code aéroport : New York, Dakar, MNL…"
          onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
          role="combobox" aria-expanded={open && suggestions.length > 0} aria-controls="dest-list" />
        <button className="btn primary" type="submit">Étudier le marché</button>
        {open && suggestions.length > 0 && (
          <ul id="dest-list" className="suggest" role="listbox">
            {suggestions.map((r) => (
              <li key={r.iata} role="option" aria-selected="false">
                <button type="button" onClick={() => load(r.iata)}>
                  <span className="code">{r.iata}</span>
                  <span>{r.ville ?? r.iata}<small>{r.aeroport}</small></span>
                  <span className={`badge ${STATUS[r.statut as keyof typeof STATUS]?.tone ?? "tpl"}`}>{STATUS[r.statut as keyof typeof STATUS]?.label}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </form>
      {examples.length > 0 && (
        <p className="examples">
          Exemples :{" "}
          {examples.map((r) => (
            <button key={r.iata} type="button" className="pill-btn" onClick={() => load(r.iata)}>{r.ville ?? r.iata}</button>
          ))}
        </p>
      )}

      {state === "loading" && (
        <div className="loading"><i className="live-dot" /> {api ? "Requêtes en cours sur BigQuery…" : "Chargement…"}</div>
      )}
      {state === "error" && <div className="callout"><p>{message}</p></div>}

      {state === "ok" && s && st && (
        <div className="study">
          <div className="study-head">
            <div>
              <p className="eyebrow">{s.pays} · {s.distance_km ? `${nf.format(s.distance_km)} km de CDG` : "distance n.d."}</p>
              <h2>{s.ville} <span className="code big">{s.iata}</span></h2>
              <p className="muted">{s.aeroport}</p>
            </div>
            <div className="head-badges">
              <span className={`badge ${st.tone}`}>{st.label}</span>
              {mode === "live" ? (
                <button type="button" className="src live" onClick={() => setShowQueries((v) => !v)}>
                  <i className="live-dot" /> En direct · BigQuery · {s.requetes?.length ?? 0} requêtes · {bytes(bytesRead)} lus
                  {elapsed ? ` · ${(elapsed / 1000).toFixed(1).replace(".", ",")} s` : ""}
                </button>
              ) : (
                <span className="src">{s.source ?? "Données exportées"}</span>
              )}
            </div>
          </div>
          {showQueries && s.requetes && (
            <div className="queries-box">{s.requetes.map((r, i) => <QueryBlock q={r} key={i} />)}</div>
          )}

          <div className="kpis">
            <div className="kpi"><span>Trafic observé sur 12 mois</span><b>{nf.format(s.trafic_total_l12)}</b></div>
            <div className="kpi hl"><span>Part de Paris</span><b>{s.paris.masque ? "masquée" : s.paris.pax_l12 === 0 ? "0 %" : pct(s.paris.part)}</b></div>
            <div className="kpi"><span>Rang de Paris</span><b>{s.paris.rang ? `${s.paris.rang} / ${s.origines.filter((o) => o.reguliere).length}` : "absent"}</b></div>
            <div className="kpi"><span>Évolution sur un an</span><b>{spct(s.croissance)}</b></div>
          </div>

          <div className="lecture">
            <h3>Ce que disent les données</h3>
            <ul>{s.lecture.map((l) => <li key={l}>{l}</li>)}</ul>
            <p className="muted small">Phrases produites par des règles à partir des chiffres : aucune IA, aucune valeur inventée.</p>
          </div>

          <div className="panel-dark">
            <h3>Passagers par mois depuis 2019</h3>
            <Chart data={s.mensuel} />
          </div>

          <div className="table-box">
            <table style={{ minWidth: 720 }}>
              <thead>
                <tr><th>Origine</th><th className="num">Passagers 12 mois</th><th className="num">Évolution</th><th className="num">Remplissage</th><th className="num">Vols 12 mois</th></tr>
              </thead>
              <tbody>
                {s.origines.filter((o) => o.reguliere || o.paris).map((o) => (
                  <tr key={o.icao} className={o.paris ? "row-paris" : ""}>
                    <td>
                      <div className="dest-cell">
                        <span className="code">{o.iata}</span>
                        <div><span className="dest-name">{o.ville}</span>{o.paris && <div className="sub">{o.iata === "ORY" ? "Orly" : "Charles-de-Gaulle"}</div>}</div>
                      </div>
                    </td>
                    <td className="num">
                      <div className="meter-cell">
                        <span className="strong">{o.mois_masques >= 6 ? "masqué" : nf.format(o.pax_l12)}</span>
                        <span className="meter" aria-hidden="true"><i style={{ width: `${Math.max(3, (o.pax_l12 / maxPax) * 100)}%` }} /></span>
                      </div>
                    </td>
                    <td className="num">
                      {o.croissance == null ? <span className="delta flat">n.d.</span> :
                        <span className={`delta ${o.croissance >= 0 ? "up" : "down"}`}>{o.croissance >= 0 ? "▲" : "▼"} {spct(o.croissance)}</span>}
                    </td>
                    <td className="num">{pct(o.remplissage)}</td>
                    <td className="num">{nf.format(o.vols_l12)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {s.statut === "desservie" && s.sante && (
            <div className="callout">
              <p><b>Santé de la ligne CDG : {HEALTH[s.sante.alert] ?? s.sante.alert}.</b> Remplissage {pct(s.sante.lf_l12)}
                {s.sante.lf_delta_pts != null ? ` (${s.sante.lf_delta_pts >= 0 ? "+" : ""}${String(s.sante.lf_delta_pts).replace(".", ",")} pts sur un an)` : ""},
                trafic {spct(s.sante.growth_pax)} sur un an.</p>
            </div>
          )}

          {s.statut !== "desservie" && s.distance_km && (
            <div>
              <div className="section-head" style={{ marginBottom: 24 }}>
                <p className="eyebrow">Et si Paris ouvrait la ligne ?</p>
                <h3 style={{ fontSize: 26 }}>Simulation instantanée du compte de résultat</h3>
                <p className="muted">Même modèle que les dossiers. Marché de référence : le trafic des hubs observé ci-dessus.</p>
              </div>
              <Simulator
                key={s.iata}
                distanceKm={s.distance_km}
                marketPax={s.trafic_total_l12 || null}
                defaults={{ freq: s.scenario.freq, aircraft: s.scenario.aircraft, loadFactor: hypotheses.loadFactor, weeks: hypotheses.weeks }}
                assumptions={{ yield: hypotheses.yield, cask: hypotheses.cask, fuel: hypotheses.fuel }}
                aircraft={hypotheses.aircraft}
              />
            </div>
          )}

          <div className="actions">
            {s.dossier && <a className="btn primary" href={`/dossier/${s.iata}`}>Lire le dossier d'ouverture</a>}
            {s.statut !== "desservie" && (
              <a className="btn line" href={`/agents?q=${encodeURIComponent(`Faut-il ouvrir une ligne Paris-${s.ville} ? À quelles conditions serait-elle rentable ?`)}`}>Poser la question aux agents IA</a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
