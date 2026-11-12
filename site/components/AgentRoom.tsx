"use client";
// Salle des opérations : on regarde les six agents instruire un dossier, un par un.
//  * « Rejouer » : l'enregistrement réel d'une instruction (requêtes BigQuery, faits, textes, contrôles).
//  * « En direct » : l'API Cloud Run lance l'instruction maintenant, sur la destination choisie,
//    et le site affiche chaque agent dès qu'il a terminé (flux Server-Sent Events).
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AGENTS, type AgentName } from "@/lib/agents";
import type { JournalEntry } from "@/lib/data";
import { Highlight, QueryBlock } from "./QueryBlock";

type Run = {
  entries: Partial<Record<AgentName, JournalEntry>>;
  current: AgentName | null;
  status: "idle" | "running" | "done" | "error";
  message?: string;
  verdict?: string;
  source?: string;
  llm?: string;
  scenario?: { freq: number; aircraft: string; region: string | null };
  controls: { essai: number | null; rejets: string[] }[];
  totalMs?: number;
};

type Props = {
  api: string;
  dossiers: { iata: string; ville: string | null }[];
  initialDest?: string;
  initialMode?: "replay" | "live";
  compact?: boolean;
};

const EMPTY: Run = { entries: {}, current: null, status: "idle", controls: [] };
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function Panel({ name, entry, run }: { name: AgentName; entry?: JournalEntry; run: Run }) {
  const a = AGENTS.find((x) => x.name === name)!;
  const idx = AGENTS.findIndex((x) => x.name === name) + 1;
  const facts = Object.entries(entry?.faits ?? {});
  return (
    <div className="room-panel" aria-live="polite">
      <div className="panel-head">
        <span className="panel-num">0{idx}</span>
        <div>
          <h3>{name}</h3>
          <p>{a.role}</p>
        </div>
        {entry?.duree_ms != null && <span className="chip on">{entry.duree_ms} ms</span>}
      </div>

      <div className="io">
        <div><span>Reçoit</span><p>{a.recoit}</p></div>
        <div><span>Fait</span><p>{a.fait}</p></div>
        <div><span>Rend</span><p>{a.rend}</p></div>
      </div>

      {!entry && (
        <p className="waiting">{run.current === name ? "En cours d'exécution…" : "En attente de son tour."}</p>
      )}

      {entry?.requetes && entry.requetes.length > 0 && (
        <section>
          <h4>Requêtes envoyées à BigQuery</h4>
          {entry.requetes.map((q, i) => <QueryBlock q={q} key={i} />)}
        </section>
      )}
      {entry && name === "Économiste" && (
        <section>
          <h4>Calcul (code déterministe, aucune IA)</h4>
          <div className="mini-table">
            <table>
              <tbody>
                {(entry.formules ?? []).slice(0, 12).map((f) => (
                  <tr key={f.indicateur}>
                    <td>{f.indicateur}</td>
                    <td className="formula">{f.formule}</td>
                    <td className="num">{new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 3 }).format(f.valeur)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {entry && name === "Avocat du diable" && entry.regles && (
        <section>
          <h4>Règles déclenchées</h4>
          <ul className="rules">
            {entry.regles.map((r) => (
              <li key={r.code}><span className={`sev ${r.gravite}`}>{r.gravite}</span><span>{r.texte}</span></li>
            ))}
          </ul>
        </section>
      )}
      {facts.length > 0 && name !== "Rédacteur" && (
        <section>
          <h4>Faits produits ({facts.length})</h4>
          <div className="mini-table">
            <table>
              <tbody>
                {facts.filter(([k]) => !k.startsWith("alerte")).slice(0, 14).map(([k, f]) => (
                  <tr key={k}>
                    <td>{f.libelle}</td>
                    <td className="tagcell"><mark className="tag">{`{{${k}}}`}</mark></td>
                    <td className="num">{f.valeur}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {entry && name === "Rédacteur" && (
        <section>
          <h4>Brouillons de l'IA et garde-fou</h4>
          {(entry.essais ?? []).length === 0 && <p className="muted-d">{entry.statut}</p>}
          {(entry.essais ?? []).map((e, i) => (
            <div className="draft" key={i}>
              <div className="chips">
                <span className="chip">Essai {e.essai ?? i + 1}</span>
                {e.duree_ms != null && <span className="chip">{(e.duree_ms / 1000).toFixed(1).replace(".", ",")} s</span>}
                <span className={`chip ${e.rejets.length ? "bad" : "good"}`}>{e.rejets.length ? "rejeté" : "contrôle réussi"}</span>
              </div>
              {e.brouillon && <pre className="code prose-code"><Highlight text={e.brouillon.slice(0, 1400)} /></pre>}
              {e.rejets.map((r) => <p className="reject" key={r}>Motif : {r}</p>)}
            </div>
          ))}
          <p className="muted-d">
            {entry.statut.startsWith("rédigé")
              ? `Rédigé par ${entry.llm}. Les balises surlignées sont remplacées par les valeurs calculées :`
              : "IA indisponible : la note est produite par le gabarit contrôlé :"}
          </p>
          <div className="final-note">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.texte ?? ""}</ReactMarkdown>
          </div>
        </section>
      )}
      {entry?.texte && name !== "Rédacteur" && (
        <section>
          <h4>Texte transmis au rédacteur</h4>
          <blockquote>{entry.texte}</blockquote>
        </section>
      )}
    </div>
  );
}

export function AgentRoom({ api, dossiers, initialDest, initialMode = "replay", compact = false }: Props) {
  const [mode, setMode] = useState<"replay" | "live">(api ? initialMode : "replay");
  const [dest, setDest] = useState((initialDest ?? dossiers[0]?.iata ?? "").toUpperCase());
  const [run, setRun] = useState<Run>(EMPTY);
  const [selected, setSelected] = useState<AgentName>("Éclaireur");
  const token = useRef(0);
  const source = useRef<EventSource | null>(null);

  useEffect(() => {
    const d = new URLSearchParams(window.location.search).get("dest");
    if (d && /^[A-Za-z]{3}$/.test(d)) {
      setDest(d.toUpperCase());
      if (api && !dossiers.some((x) => x.iata === d.toUpperCase())) setMode("live");
    }
    return () => source.current?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const replay = useCallback(async () => {
    const my = ++token.current;
    source.current?.close();
    setRun({ ...EMPTY, status: "running" });
    let d: { journal: JournalEntry[]; verdict: string; source_donnees?: string; scenario?: Run["scenario"] };
    try {
      const res = await fetch(`/dossiers/${dest}.json`);
      if (!res.ok) throw new Error();
      d = await res.json();
    } catch {
      setRun({ ...EMPTY, status: "error", message: `Aucun enregistrement pour ${dest}. Choisissez une destination du radar, ou passez en direct.` });
      return;
    }
    setRun((r) => ({ ...r, source: d.source_donnees, scenario: d.scenario, llm: d.journal.find((j) => j.agent === "Rédacteur")?.llm }));
    let total = 0;
    for (const a of AGENTS) {
      if (token.current !== my) return;
      const entry = d.journal.find((j) => j.agent === a.name);
      setRun((r) => ({ ...r, current: a.name }));
      setSelected(a.name);
      await sleep(compact ? 650 : 1100);
      if (token.current !== my) return;
      total += entry?.duree_ms ?? 0;
      setRun((r) => ({ ...r, entries: { ...r.entries, [a.name]: entry } }));
      await sleep(compact ? 350 : 700);
    }
    setRun((r) => ({ ...r, current: null, status: "done", verdict: d.verdict, totalMs: total }));
  }, [dest, compact]);

  const live = useCallback(() => {
    if (!api) return;
    ++token.current;
    source.current?.close();
    setRun({ ...EMPTY, status: "running" });
    setSelected("Éclaireur");
    const es = new EventSource(`${api}/instruire?dest=${encodeURIComponent(dest)}`);
    source.current = es;
    let finished = false;
    es.onmessage = (msg) => {
      const ev = JSON.parse(msg.data);
      if (ev.type === "scenario") setRun((r) => ({ ...r, scenario: ev.scenario, llm: ev.llm, source: ev.source }));
      if (ev.type === "debut") {
        setRun((r) => ({ ...r, current: ev.agent }));
        setSelected(ev.agent);
      }
      if (ev.type === "agent") setRun((r) => ({ ...r, entries: { ...r.entries, [ev.entree.agent]: ev.entree } }));
      if (ev.type === "controle") setRun((r) => ({ ...r, controls: [...r.controls, { essai: ev.essai, rejets: ev.rejets }] }));
      if (ev.type === "erreur") {
        finished = true;
        es.close();
        setRun((r) => ({ ...r, status: "error", current: null, message: ev.message }));
      }
      if (ev.type === "fin") {
        finished = true;
        es.close();
        setRun((r) => ({ ...r, status: "done", current: null, verdict: ev.dossier.verdict, totalMs: ev.t_ms }));
        setSelected("Rédacteur");
      }
    };
    es.onerror = () => {
      es.close();
      if (!finished)
        setRun((r) => ({ ...r, status: "error", current: null,
          message: "L'API Cloud Run ne répond pas (limite de demandes atteinte ou service arrêté). Le mode « Rejouer » reste disponible." }));
    };
  }, [api, dest]);

  const start = () => (mode === "live" ? live() : replay());
  const doneCount = Object.keys(run.entries).length;

  return (
    <div className={`room${compact ? " compact" : ""}`}>
      <div className="room-bar">
        <div className="seg" role="tablist" aria-label="Mode">
          <button role="tab" aria-selected={mode === "replay"} className={mode === "replay" ? "on" : ""} onClick={() => setMode("replay")}>
            Rejouer un enregistrement
          </button>
          <button role="tab" aria-selected={mode === "live"} className={mode === "live" ? "on" : ""} onClick={() => setMode("live")} disabled={!api}
            title={api ? "" : "API non configurée"}>
            <i className="live-dot" /> En direct sur GCP
          </button>
        </div>
        <label className="dest-input">
          <span>Destination</span>
          {mode === "replay" ? (
            <select value={dest} onChange={(e) => setDest(e.target.value)}>
              {dossiers.map((d) => <option key={d.iata} value={d.iata}>{d.ville ?? d.iata} ({d.iata})</option>)}
            </select>
          ) : (
            <>
              <input value={dest} maxLength={3} onChange={(e) => setDest(e.target.value.toUpperCase().replace(/[^A-Z]/g, ""))}
                list="room-dests" placeholder="ex. DSS" aria-describedby="dest-help" />
              <datalist id="room-dests">
                {dossiers.map((d) => <option key={d.iata} value={d.iata}>{d.ville}</option>)}
              </datalist>
            </>
          )}
        </label>
        <button className="btn primary" onClick={start} disabled={run.status === "running" || dest.length !== 3}>
          {run.status === "running" ? "Instruction en cours…" : "Lancer l'instruction"}
        </button>
      </div>
      {mode === "live" && (
        <p id="dest-help" className="room-help">
          N'importe quel code IATA, même hors radar (DSS pour Dakar, BOG pour Bogota…). Les agents interrogent BigQuery
          maintenant, l'IA rédige, le garde-fou contrôle.
        </p>
      )}

      <div className="room-status">
        <div className="progress"><i style={{ width: `${(doneCount / AGENTS.length) * 100}%` }} /></div>
        <span>
          {run.status === "idle" && "Prêt."}
          {run.status === "running" && `${doneCount} agent${doneCount > 1 ? "s" : ""} sur 6 · ${run.current ?? ""}`}
          {run.status === "done" && `Terminé${run.totalMs ? ` en ${(run.totalMs / 1000).toFixed(1).replace(".", ",")} s` : ""}`}
          {run.status === "error" && run.message}
        </span>
        {run.scenario && (
          <span className="room-meta">
            Scénario : {run.scenario.freq} A/R par semaine en {run.scenario.aircraft}
            {run.llm ? ` · IA : ${run.llm}` : ""}{run.source ? ` · données : ${run.source}` : ""}
          </span>
        )}
      </div>

      <div className="room-grid">
        <ol className="room-agents">
          {AGENTS.map((a, i) => {
            const e = run.entries[a.name];
            const state = e ? "done" : run.current === a.name ? "active" : "wait";
            return (
              <li key={a.name}>
                <button className={`agent-step ${state}${selected === a.name ? " sel" : ""}`} onClick={() => setSelected(a.name)}
                  aria-current={selected === a.name ? "step" : undefined}>
                  <span className="step-num">0{i + 1}</span>
                  <span className="step-body">
                    <b>{a.name}</b>
                    <small>
                      {state === "done" && `${e?.requetes?.length ?? 0} requête${(e?.requetes?.length ?? 0) > 1 ? "s" : ""} · ${Object.keys(e?.faits ?? {}).length} faits`}
                      {state === "active" && "au travail…"}
                      {state === "wait" && a.role}
                    </small>
                  </span>
                  <span className="step-state" aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ol>
        <Panel name={selected} entry={run.entries[selected]} run={run} />
      </div>

      {run.status === "done" && run.verdict && (
        <div className="room-verdict">
          <span>Recommandation</span>
          <b>{run.verdict}</b>
          {dossiers.some((d) => d.iata === dest) && <a className="btn ghost" href={`/dossier/${dest}`}>Ouvrir le dossier complet</a>}
        </div>
      )}
    </div>
  );
}
