"use client";
// Simulateur : l'analyste modifie les hypothèses, le compte de résultat se recalcule aussitôt.
// Mêmes formules que le modèle Python (voir lib/economics.ts).
import { useMemo, useState } from "react";
import { evaluate, sensitivity, type Inputs } from "@/lib/economics";
import { int, meur, pct } from "@/lib/format";

type Aircraft = Record<string, { seats: number; cabins?: string }>;

type Props = {
  distanceKm: number;
  marketPax: number | null;
  defaults: { freq: number; aircraft: string; loadFactor: number; weeks: number };
  assumptions: { yield: number; cask: number; fuel: number };
  aircraft: Aircraft;
};

export function Simulator({ distanceKm, marketPax, defaults, assumptions, aircraft }: Props) {
  const [freq, setFreq] = useState(defaults.freq);
  const [plane, setPlane] = useState(defaults.aircraft);
  const [lf, setLf] = useState(Math.round(defaults.loadFactor * 1000) / 10);
  const [yieldChange, setYieldChange] = useState(0);
  const [fuelChange, setFuelChange] = useState(0);
  const [weeks, setWeeks] = useState(defaults.weeks);

  const inputs: Inputs = useMemo(
    () => ({
      distanceKm,
      frequenciesPerWeek: freq,
      seatsPerFlight: aircraft[plane]?.seats ?? 300,
      loadFactor: lf / 100,
      yieldEurPerRpk: assumptions.yield * (1 + yieldChange / 100),
      costEurPerAsk: assumptions.cask,
      fuelEurPerAsk: assumptions.fuel,
      weeksPerYear: weeks,
      fuelPriceChange: fuelChange / 100,
      marketPaxPerYear: marketPax,
    }),
    [distanceKm, freq, plane, lf, yieldChange, fuelChange, weeks, aircraft, assumptions, marketPax],
  );
  const r = evaluate(inputs);
  const sens = sensitivity(inputs);
  const maxAbs = Math.max(1, ...sens.flatMap((s) => [Math.abs(s.low), Math.abs(s.high)]));
  const toPct = (v: number) => 50 + (v / maxAbs) * 50;
  const negative = r.operatingResult < 0;

  const reset = () => {
    setFreq(defaults.freq);
    setPlane(defaults.aircraft);
    setLf(Math.round(defaults.loadFactor * 1000) / 10);
    setYieldChange(0);
    setFuelChange(0);
    setWeeks(defaults.weeks);
  };

  return (
    <div className="sim">
      <form className="controls" aria-label="Hypothèses du scénario" onSubmit={(e) => e.preventDefault()}>
        <div className="control">
          <label htmlFor="freq">Allers-retours par semaine <output htmlFor="freq">{freq}</output></label>
          <input id="freq" type="range" min={1} max={14} step={1} value={freq} onChange={(e) => setFreq(+e.target.value)} />
          <small>Un aller-retour hebdomadaire représente deux vols.</small>
        </div>
        <div className="control">
          <label htmlFor="plane">Appareil</label>
          <select id="plane" value={plane} onChange={(e) => setPlane(e.target.value)}>
            {Object.entries(aircraft).map(([name, a]) => (
              <option key={name} value={name}>{name} · {a.seats} sièges</option>
            ))}
          </select>
        </div>
        <div className="control">
          <label htmlFor="lf">Remplissage visé <output htmlFor="lf">{lf.toFixed(1).replace(".", ",")} %</output></label>
          <input id="lf" type="range" min={60} max={95} step={0.5} value={lf} onChange={(e) => setLf(+e.target.value)} />
          <small>Par défaut : moyenne publiée par Air France-KLM pour la région.</small>
        </div>
        <div className="control">
          <label htmlFor="yield">Recette par passager-km <output htmlFor="yield">{yieldChange > 0 ? "+" : ""}{yieldChange} %</output></label>
          <input id="yield" type="range" min={-30} max={30} step={1} value={yieldChange} onChange={(e) => setYieldChange(+e.target.value)} />
          <small>Écart par rapport à la moyenne du réseau. Les longues lignes rapportent souvent moins par kilomètre.</small>
        </div>
        <div className="control">
          <label htmlFor="fuel">Prix du carburant <output htmlFor="fuel">{fuelChange > 0 ? "+" : ""}{fuelChange} %</output></label>
          <input id="fuel" type="range" min={-40} max={60} step={5} value={fuelChange} onChange={(e) => setFuelChange(+e.target.value)} />
        </div>
        <div className="control">
          <label htmlFor="weeks">Semaines d'exploitation par an <output htmlFor="weeks">{weeks}</output></label>
          <input id="weeks" type="range" min={12} max={52} step={1} value={weeks} onChange={(e) => setWeeks(+e.target.value)} />
          <small>Moins de 52 : ligne saisonnière.</small>
        </div>
        <button type="button" className="btn line" onClick={reset}>Revenir au scénario de départ</button>
      </form>

      <div style={{ display: "grid", gap: 20 }} aria-live="polite">
        <div className="kpis">
          <div className="kpi"><span>Passagers par an</span><b>{int(r.passengers)}</b></div>
          <div className="kpi"><span>Recette annuelle</span><b>{meur(r.revenue)}</b></div>
          <div className="kpi"><span>Coûts annuels</span><b>{meur(r.totalCost)}</b></div>
          <div className={`kpi hl${negative ? " neg" : ""}`}><span>Résultat d'exploitation</span><b>{meur(r.operatingResult)}</b></div>
          <div className="kpi"><span>Marge</span><b>{pct(r.margin)}</b></div>
          <div className="kpi"><span>Part de marché à conquérir</span><b>{pct(r.marketShare)}</b></div>
        </div>

        <div className="card">
          <h3>Remplissage visé et point d'équilibre</h3>
          <p>
            La ligne gagne de l'argent si le remplissage visé dépasse le remplissage d'équilibre
            ({pct(r.breakevenLoadFactor)}).{" "}
            {negative ? "Ce n'est pas le cas dans ce scénario." : `Marge de sécurité : ${(lf - r.breakevenLoadFactor * 100).toFixed(1).replace(".", ",")} points.`}
          </p>
          <div className="gauge" role="img" aria-label={`Remplissage visé ${lf} %, équilibre ${pct(r.breakevenLoadFactor)}`}>
            <div className="fill" style={{ width: `${Math.min(100, lf)}%`, background: negative ? "#b3232c" : undefined }} />
            <div className="be" style={{ left: `${Math.min(100, r.breakevenLoadFactor * 100)}%` }}>
              <span>équilibre</span>
            </div>
          </div>
        </div>

        <div className="card">
          <h3>Ce qui fait bouger le résultat</h3>
          <p>Effet de chaque hypothèse sur le résultat annuel, de la plus influente à la moins influente. Rouge : scénario défavorable ; bleu : favorable.</p>
          <div className="tornado">
            {sens.map((s) => {
              const lo = Math.min(s.low, s.high), hi = Math.max(s.low, s.high);
              const base = r.operatingResult;
              return (
                <div className="row" key={s.label}>
                  <span className="small" style={{ fontWeight: 600 }}>{s.label}</span>
                  <div className="bar">
                    <i className="lo" style={{ left: `${toPct(Math.min(lo, base))}%`, width: `${Math.abs(toPct(base) - toPct(lo))}%` }} />
                    <i className="hi" style={{ left: `${toPct(base)}%`, width: `${Math.abs(toPct(hi) - toPct(base))}%` }} />
                    <span className="axis" style={{ left: `${toPct(0)}%` }} title="zéro" />
                  </div>
                  <div className="vals"><span>{meur(lo)}</span><span>{meur(hi)}</span></div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
