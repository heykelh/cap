"use client";
// Le SQL réellement exécuté par BigQuery pour construire chaque table.
import { useState } from "react";

export function SqlViewer({ files }: { files: { couche: string; fichier: string; table: string; sql: string }[] }) {
  const [i, setI] = useState(0);
  if (!files.length) return null;
  const f = files[i];
  return (
    <div className="sqlv">
      <div className="sqlv-tabs" role="tablist" aria-label="Fichiers SQL">
        {files.map((x, j) => (
          <button key={x.fichier + x.couche} role="tab" aria-selected={i === j} className={i === j ? "on" : ""} onClick={() => setI(j)}>
            <small>{x.couche}</small>{x.table.split(".")[1]}
          </button>
        ))}
      </div>
      <div className="sqlv-body">
        <p className="params">transform/sql/{f.couche}/{f.fichier} → table <b>{f.table}</b></p>
        <pre className="code tall"><code>{f.sql}</code></pre>
      </div>
    </div>
  );
}
