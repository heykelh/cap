"use client";
// Vérification en direct de l'API Cloud Run : temps de réponse et aller-retour BigQuery.
import { useState } from "react";

type Health = { statut: string; source: string; projet?: string; cloud_run?: string; revision?: string;
  bigquery?: { duree_ms: number; job_id: string } };

export function ApiStatus({ api }: { api: string }) {
  const [h, setH] = useState<Health | null>(null);
  const [ms, setMs] = useState<number | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "ok" | "error">("idle");

  async function check() {
    setState("loading");
    const t0 = performance.now();
    try {
      const res = await fetch(`${api}/health?bigquery=1`, { cache: "no-store" });
      if (!res.ok) throw new Error();
      setH(await res.json());
      setMs(performance.now() - t0);
      setState("ok");
    } catch {
      setState("error");
    }
  }

  if (!api) {
    return <p className="muted-d">API non configurée sur ce déploiement : le site fonctionne sur les données exportées.</p>;
  }
  return (
    <div className="api-status">
      <button className="btn primary" onClick={check} disabled={state === "loading"}>
        {state === "loading" ? "Appel en cours…" : "Tester l'API maintenant"}
      </button>
      {state === "ok" && h && (
        <dl className="status-grid">
          <div><dt>Réponse complète</dt><dd>{Math.round(ms ?? 0)} ms</dd></div>
          <div><dt>Aller-retour BigQuery</dt><dd>{h.bigquery ? `${h.bigquery.duree_ms} ms` : "n.d."}</dd></div>
          <div><dt>Service Cloud Run</dt><dd>{h.cloud_run ?? "local"}</dd></div>
          <div><dt>Révision</dt><dd>{h.revision ?? "n.d."}</dd></div>
          <div><dt>Projet GCP</dt><dd>{h.projet ?? "n.d."}</dd></div>
          <div><dt>Job BigQuery</dt><dd className="mono-cell">{h.bigquery?.job_id ?? "n.d."}</dd></div>
        </dl>
      )}
      {state === "error" && (
        <p className="reject">Pas de réponse. Le service a peut-être été arrêté ou la limite de demandes est atteinte.</p>
      )}
      {state === "ok" && ms && ms > 3000 && (
        <p className="muted-d">Premier appel plus lent : Cloud Run démarre une instance à la demande, puis répond en quelques dizaines de millisecondes.</p>
      )}
    </div>
  );
}
