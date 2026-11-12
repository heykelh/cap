"use client";
// Affichage d'une requête BigQuery exécutée par CAP : texte SQL, paramètres, octets lus, durée.
import type { Requete } from "@/lib/data";

export function bytes(n: number) {
  if (!n) return "0 octet";
  if (n < 1e6) return `${(n / 1e3).toFixed(1).replace(".", ",")} Ko`;
  if (n < 1e9) return `${(n / 1e6).toFixed(1).replace(".", ",")} Mo`;
  return `${(n / 1e9).toFixed(2).replace(".", ",")} Go`;
}

export function Highlight({ text }: { text: string }) {
  const parts = text.split(/(\{\{\s*[a-z0-9_]+\s*\}\})/g);
  return (
    <>
      {parts.map((p, i) => (p.startsWith("{{") ? <mark className="tag" key={i}>{p}</mark> : <span key={i}>{p}</span>))}
    </>
  );
}

export function QueryBlock({ q }: { q: Requete }) {
  const live = q.execute_sur === "BigQuery";
  return (
    <div className="query">
      <div className="chips">
        <span className={`chip ${live ? "on" : ""}`}>{live ? "Exécutée sur BigQuery" : "Lue dans l'instantané exporté de BigQuery"}</span>
        {live && <span className="chip">{bytes(q.octets_lus)} lus</span>}
        {live && <span className="chip">{q.duree_ms} ms</span>}
        <span className="chip">{q.lignes} ligne{q.lignes > 1 ? "s" : ""}</span>
        {live && q.cache && <span className="chip">résultat en cache</span>}
        {q.job_id && <span className="chip mono-chip" title="Identifiant du job BigQuery">job {q.job_id.slice(0, 18)}…</span>}
      </div>
      <pre className="code"><code>{q.sql}</code></pre>
      {Object.keys(q.parametres || {}).length > 0 && (
        <p className="params">
          Paramètres :{" "}
          {Object.entries(q.parametres).map(([k, v]) => (
            <span key={k}>
              <b>@{k}</b> = {Array.isArray(v) ? `[${(v as string[]).join(", ")}]` : String(v)}{" "}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

