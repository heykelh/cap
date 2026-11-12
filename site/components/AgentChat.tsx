"use client";
// Les agents IA en action : l'Analyste et le Contradicteur décident eux-mêmes quels outils appeler.
//  * « En direct » : l'API Cloud Run fait tourner les agents maintenant (flux Server-Sent Events).
//  * « Rejouer » : une session réelle enregistrée lors du dernier rafraîchissement.
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Requete } from "@/lib/data";
import { Highlight, QueryBlock, bytes } from "./QueryBlock";

type Ref = { valeur: string; ref: string };
type Ev =
  | { type: "debut"; question: string; llm: string; t_ms?: number }
  | { type: "tour"; agent: string; tour: number; t_ms?: number }
  | { type: "message"; agent: string; texte: string; t_ms?: number }
  | { type: "appel"; agent: string; outil: string; arguments: Record<string, unknown>; t_ms?: number }
  | { type: "resultat"; agent: string; outil: string; ok: boolean; resultat: Record<string, unknown>; requetes: Requete[]; duree_ms: number; t_ms?: number }
  | { type: "garde_fou"; agent: string; ok: boolean; rejets: string[]; brouillon: string; t_ms?: number }
  | { type: "verdict"; agent: string; verdict: "valide" | "a_revoir"; objections_affichees: string[]; t_ms?: number }
  | { type: "reponse"; texte: string; brouillon: string; secours: boolean; faits: { ref: string; valeur: string; libelle: string; outil: string }[]; t_ms?: number }
  | { type: "fin"; duree_ms: number; appels_outils: number; tours_contradicteur: number; llm: string; requetes_bigquery: number; octets_lus: number; t_ms?: number }
  | { type: "erreur"; message: string; detail?: string; t_ms?: number };

type Example = { id: string; question: string; ok: boolean };

const TOOL_LABEL: Record<string, string> = {
  chercher_destinations: "Chercher dans le radar",
  etude_marche: "Étude de marché",
  simuler_ligne: "Simuler la ligne",
  sensibilites: "Sensibilités",
};
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function isRef(v: unknown): v is Ref {
  return !!v && typeof v === "object" && "valeur" in (v as object) && "ref" in (v as object);
}

function Value({ v }: { v: unknown }): React.ReactNode {
  if (isRef(v)) return <span className="val"><b>{v.valeur}</b><mark className="tag">{v.ref}</mark></span>;
  if (Array.isArray(v)) return <div className="val-list">{v.map((x, i) => <div key={i} className="val-item"><Value v={x} /></div>)}</div>;
  if (v && typeof v === "object")
    return (
      <dl className="val-obj">
        {Object.entries(v as Record<string, unknown>).map(([k, x]) => (
          <div key={k}><dt>{k.replace(/_/g, " ")}</dt><dd><Value v={x} /></dd></div>
        ))}
      </dl>
    );
  if (typeof v === "boolean") return <span>{v ? "oui" : "non"}</span>;
  return <span>{String(v ?? "")}</span>;
}

function ResultCard({ ev }: { ev: Extract<Ev, { type: "resultat" }> }) {
  const [open, setOpen] = useState(false);
  const live = ev.requetes.filter((q) => q.execute_sur === "BigQuery");
  const read = ev.requetes.reduce((a, q) => a + (q.octets_lus || 0), 0);
  return (
    <div className={`ev-result${ev.ok ? "" : " ko"}`}>
      <div className="chips">
        <span className={`chip ${ev.ok ? "good" : "bad"}`}>{ev.ok ? "résultat" : "erreur renvoyée à l'agent"}</span>
        {ev.requetes.length > 0 && (
          <span className="chip on">{live.length ? `${live.length} requête${live.length > 1 ? "s" : ""} BigQuery · ${bytes(read)} lus` : `${ev.requetes.length} lecture${ev.requetes.length > 1 ? "s" : ""} de l'instantané`}</span>
        )}
        <span className="chip">{ev.duree_ms} ms</span>
        {ev.requetes.length > 0 && (
          <button type="button" className="chip link" onClick={() => setOpen((o) => !o)}>{open ? "masquer le SQL" : "voir le SQL"}</button>
        )}
      </div>
      <div className="ev-values"><Value v={ev.resultat} /></div>
      {open && <div className="ev-sql">{ev.requetes.map((q, i) => <QueryBlock q={q} key={i} />)}</div>}
    </div>
  );
}

function Draft({ ev }: { ev: Extract<Ev, { type: "garde_fou" }> }) {
  const [open, setOpen] = useState(!ev.ok);
  return (
    <div className={`ev-guard ${ev.ok ? "ok" : "ko"}`}>
      <div className="ev-guard-head">
        <span className="guard-icon" aria-hidden="true">{ev.ok ? "✓" : "✕"}</span>
        <b>Garde-fou : {ev.ok ? "réponse acceptée, chaque chiffre provient d'un outil" : "réponse rejetée, renvoyée à l'Analyste"}</b>
        <button type="button" className="chip link" onClick={() => setOpen((o) => !o)}>{open ? "masquer" : "voir le brouillon"}</button>
      </div>
      {ev.rejets.map((r) => <p className="reject" key={r}>Motif : {r}</p>)}
      {open && <pre className="code prose-code"><Highlight text={ev.brouillon} /></pre>}
    </div>
  );
}

export function AgentChat({ api, examples, initialQuestion }: { api: string; examples: Example[]; initialQuestion?: string }) {
  const [mode, setMode] = useState<"live" | "replay">(api ? "live" : "replay");
  const [question, setQuestion] = useState(initialQuestion ?? examples[0]?.question ?? "");
  const [events, setEvents] = useState<Ev[]>([]);
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [replayId, setReplayId] = useState(examples[0]?.id ?? "");
  const token = useRef(0);
  const es = useRef<EventSource | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) {
      setQuestion(q);
      if (api) setMode("live");
    }
    return () => es.current?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const push = (e: Ev) => setEvents((prev) => [...prev, e]);
  const stats = {
    outils: events.filter((e) => e.type === "appel").length,
    requetes: events.reduce((a, e) => a + (e.type === "resultat" ? e.requetes.filter((q) => q.execute_sur === "BigQuery").length : 0), 0),
    octets: events.reduce((a, e) => a + (e.type === "resultat" ? e.requetes.reduce((b, q) => b + (q.octets_lus || 0), 0) : 0), 0),
    t: events.length ? (events[events.length - 1].t_ms ?? 0) : 0,
  };
  const current = [...events].reverse().find((e) => e.type === "tour") as Extract<Ev, { type: "tour" }> | undefined;

  function startLive() {
    const my = ++token.current;
    es.current?.close();
    setEvents([]);
    setStatus("running");
    const source = new EventSource(`${api}/analyste?question=${encodeURIComponent(question)}`);
    es.current = source;
    let done = false;
    source.onmessage = (m) => {
      if (my !== token.current) return;
      const e = JSON.parse(m.data) as Ev;
      push(e);
      if (e.type === "fin" || e.type === "erreur") {
        done = true;
        source.close();
        setStatus(e.type === "fin" ? "done" : "error");
      }
    };
    source.onerror = () => {
      source.close();
      if (!done && my === token.current) {
        push({ type: "erreur", message: "L'API ne répond pas (service arrêté ou limite de demandes atteinte). Le mode « Rejouer » reste disponible." });
        setStatus("error");
      }
    };
  }

  async function startReplay() {
    const my = ++token.current;
    es.current?.close();
    setEvents([]);
    setStatus("running");
    try {
      const res = await fetch(`/analyste/${replayId}.json`);
      const data = (await res.json()) as { question: string; evenements: Ev[] };
      setQuestion(data.question);
      let last = 0;
      for (const e of data.evenements) {
        const wait = Math.min(1600, Math.max(350, ((e.t_ms ?? last) - last) / 3));
        last = e.t_ms ?? last;
        await sleep(wait);
        if (my !== token.current) return;
        push(e);
      }
      setStatus("done");
    } catch {
      push({ type: "erreur", message: "Session enregistrée introuvable." });
      setStatus("error");
    }
  }

  useEffect(() => {
    if (status === "running") bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [events.length, status]);

  return (
    <div className="chat">
      <div className="chat-ask">
        <div className="seg" role="tablist" aria-label="Mode">
          <button role="tab" aria-selected={mode === "live"} className={mode === "live" ? "on" : ""} onClick={() => setMode("live")} disabled={!api}>
            <i className="live-dot" /> En direct
          </button>
          <button role="tab" aria-selected={mode === "replay"} className={mode === "replay" ? "on" : ""} onClick={() => setMode("replay")} disabled={!examples.length}>
            Rejouer une session enregistrée
          </button>
        </div>
        {mode === "live" ? (
          <form className="ask-form" onSubmit={(e) => { e.preventDefault(); if (question.trim().length >= 8) startLive(); }}>
            <label htmlFor="q" className="sr-only">Votre question</label>
            <textarea id="q" rows={2} maxLength={400} value={question} onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ex. : Faut-il ouvrir Paris-Dakar ? Quelle destination asiatique ouvrir avec un seul A350 ?" />
            <button className="btn primary" type="submit" disabled={status === "running" || question.trim().length < 8}>
              {status === "running" ? "Les agents travaillent…" : "Poser la question"}
            </button>
          </form>
        ) : (
          <div className="ask-form">
            <label htmlFor="ex" className="sr-only">Session</label>
            <select id="ex" value={replayId} onChange={(e) => setReplayId(e.target.value)}>
              {examples.map((x) => <option key={x.id} value={x.id}>{x.question}</option>)}
            </select>
            <button className="btn primary" onClick={startReplay} disabled={status === "running"}>
              {status === "running" ? "Lecture…" : "Rejouer"}
            </button>
          </div>
        )}
        {mode === "live" && examples.length > 0 && (
          <p className="examples dark-ex">
            Idées :{" "}
            {examples.map((x) => (
              <button key={x.id} type="button" className="pill-btn" onClick={() => setQuestion(x.question)}>{x.question}</button>
            ))}
          </p>
        )}
      </div>

      <div className="chat-stats">
        <span className={`who ${current?.agent === "Contradicteur" ? "critic" : ""}`}>
          {status === "running" ? <><i className="live-dot" /> {current?.agent ?? "Analyste"} au travail</> : status === "done" ? "Terminé" : status === "error" ? "Interrompu" : "Prêt"}
        </span>
        <span><b>{stats.outils}</b> appels d'outils</span>
        <span><b>{stats.requetes}</b> requêtes BigQuery</span>
        <span><b>{bytes(stats.octets)}</b> lus</span>
        <span><b>{(stats.t / 1000).toFixed(1).replace(".", ",")} s</b></span>
      </div>

      <ol className="feed" aria-live="polite">
        {events.map((e, i) => {
          if (e.type === "debut") return <li key={i} className="ev-q"><span>Question</span><p>{e.question}</p><small>Modèle : {e.llm}</small></li>;
          if (e.type === "tour")
            return (
              <li key={i} className={`ev-turn ${e.agent === "Contradicteur" ? "critic" : ""}`}>
                {e.agent === "Contradicteur" ? "Le Contradicteur relit la réponse et vérifie" : e.tour > 1 ? "L'Analyste répond aux objections" : "L'Analyste prend la question"}
              </li>
            );
          if (e.type === "message")
            return (
              <li key={i} className={`ev-msg ${e.agent === "Contradicteur" ? "critic" : ""}`}>
                <span className="avatar">{e.agent === "Contradicteur" ? "C" : "A"}</span>
                <div><small>{e.agent} · décide</small><p>{e.texte}</p></div>
              </li>
            );
          if (e.type === "appel")
            return (
              <li key={i} className={`ev-call ${e.agent === "Contradicteur" ? "critic" : ""}`}>
                <span className="arrow">→</span>
                <span>{e.agent} appelle <b>{TOOL_LABEL[e.outil] ?? e.outil}</b></span>
                <code>{e.outil}({Object.entries(e.arguments).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(", ")})</code>
              </li>
            );
          if (e.type === "resultat") return <li key={i}><ResultCard ev={e} /></li>;
          if (e.type === "garde_fou") return <li key={i}><Draft ev={e} /></li>;
          if (e.type === "verdict")
            return (
              <li key={i} className={`ev-verdict ${e.verdict}`}>
                <span className="avatar">C</span>
                <div>
                  <small>Contradicteur · verdict</small>
                  <b>{e.verdict === "valide" ? "Réponse validée" : "Réponse contestée : l'Analyste doit revoir sa copie"}</b>
                  {e.objections_affichees.length > 0 && <ul>{e.objections_affichees.map((o) => <li key={o}>{o}</li>)}</ul>}
                </div>
              </li>
            );
          if (e.type === "reponse")
            return (
              <li key={i} className="ev-answer">
                <div className="answer-head"><span>Réponse finale {e.secours ? "(secours : chiffres bruts des outils)" : "de l'Analyste"}</span></div>
                <div className="final-note"><ReactMarkdown remarkPlugins={[remarkGfm]}>{e.texte}</ReactMarkdown></div>
                {e.faits.length > 0 && (
                  <div className="mini-table">
                    <table>
                      <thead><tr><th>Référence</th><th>Chiffre cité</th><th className="num">Valeur</th><th>Outil</th></tr></thead>
                      <tbody>
                        {e.faits.map((f) => (
                          <tr key={f.ref}><td><mark className="tag">{`{{${f.ref}}}`}</mark></td><td>{f.libelle}</td><td className="num">{f.valeur}</td><td>{TOOL_LABEL[f.outil] ?? f.outil}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </li>
            );
          if (e.type === "fin")
            return (
              <li key={i} className="ev-end">
                Terminé en {(e.duree_ms / 1000).toFixed(1).replace(".", ",")} s · {e.appels_outils} appels d'outils ·{" "}
                {e.tours_contradicteur} relecture{e.tours_contradicteur > 1 ? "s" : ""} du Contradicteur · {e.llm}
              </li>
            );
          if (e.type === "erreur")
            return (
              <li key={i} className="ev-error">
                {e.message}
                {e.detail && <details><summary>Détail technique</summary>{e.detail}</details>}
              </li>
            );
          return null;
        })}
        {status === "running" && <li className="ev-typing"><i /><i /><i /></li>}
        <div ref={bottom} />
      </ol>
      {status === "idle" && (
        <p className="chat-empty">
          {mode === "live" ? "Posez une question : les agents vont choisir eux-mêmes quelles données consulter." : "Choisissez une session puis lancez la lecture."}
        </p>
      )}
    </div>
  );
}
