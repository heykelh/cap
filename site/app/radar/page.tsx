import Link from "next/link";
import type { Metadata } from "next";
import { WorldMap } from "@/components/WorldMap";
import { getMeta, getRadar } from "@/lib/data";
import { ALERT_LABELS, int, km, meurFromM, month, signedPct, verdictShort, verdictTone } from "@/lib/format";

export const metadata: Metadata = { title: "Radar des opportunités · CAP" };

export default function RadarPage() {
  const radar = getRadar();
  const meta = getMeta();
  const lastFr = meta.fraicheur_par_pays.find((f) => f.rep_country === "FR")?.last_month;
  const maxResult = Math.max(1, ...radar.map((r) => r.resultat_meur));
  const seg = meta.radar_par_segment && Object.keys(meta.radar_par_segment).length ? meta.radar_par_segment : null;
  const total = seg ? Object.values(seg).reduce((a, b) => a + b, 0) : radar.length;

  return (
    <>
      <section className="hero">
        <div className="wrap">
          <p className="eyebrow">Usage 1 · Détecter</p>
          <h1 style={{ fontSize: "clamp(38px, 5vw, 60px)" }}>Le radar des opportunités</h1>
          <p className="lead">
            Les destinations long-courrier desservies régulièrement par les grands hubs européens, mais pas par
            Paris. Pour chacune, un dossier d'ouverture complet a été instruit par la chaîne d'instruction.
          </p>
          <WorldMap rows={radar} labels={10} title="Carte des destinations du radar" />
        </div>
      </section>

      <section className="section tight">
        <div className="wrap">
          <div className="explain" style={{ marginBottom: 40 }}>
            <div className="callout">
              <p>
                <b>Comment lire le score.</b> Il va de 0 à 100 et compare les destinations d'un même segment.
                Il combine quatre critères : le volume de passagers des hubs concurrents (40 %), sa croissance
                sur un an (25 %), leur taux de remplissage (20 %) et le nombre de hubs qui desservent la
                destination (15 %).
              </p>
            </div>
            <div className="callout">
              <p>
                <b>Ce qui est exclu.</b> Les destinations déjà desservies depuis Paris CDG ou Orly, y compris par
                un autre aéroport de la même ville, et celles signalées par l'analyste. Données des hubs : douze
                derniers mois publiés par Eurostat (France : jusqu'à {month(lastFr)}).
              </p>
            </div>
          </div>

          <div className="callout" style={{ marginBottom: 28 }}>
            <p>
              <b>Pourquoi {radar.length} dossiers ?</b> Règle simple : {meta.regle_dossiers ?? "un dossier pour chaque destination long-courrier du radar"}.
              {seg ? ` Le radar compte ${total} destinations : ${Object.entries(seg).map(([k, v]) => `${v} en ${k}`).join(", ")}.` : ""}{" "}
              Le court et le moyen-courrier restent consultables dans l'<Link href="/marche">étude de marché</Link>, sans dossier : le
              modèle économique est calibré sur le long-courrier.
            </p>
          </div>
          <p className="muted small" style={{ margin: "0 0 12px" }}>
            Résultat et marge : scénario de départ de chaque dossier, modifiable dans le dossier.
          </p>
          <div className="table-box">
            <table style={{ minWidth: 880 }}>
              <thead>
                <tr>
                  <th>Rang</th>
                  <th>Destination</th>
                  <th className="num">Score</th>
                  <th className="num">Distance</th>
                  <th className="num">Passagers des hubs</th>
                  <th className="num">Évolution</th>
                  <th className="num">Résultat estimé</th>
                  <th>Recommandation</th>
                </tr>
              </thead>
              <tbody>
                {radar.map((r) => (
                  <tr key={r.iata}>
                    <td className="num rank">{String(r.rang).padStart(2, "0")}</td>
                    <td>
                      <div className="dest-cell">
                        <span className="code">{r.iata}</span>
                        <div>
                          <Link href={`/dossier/${r.iata}`} className="dest-name">
                            {r.ville ?? r.iata}
                          </Link>
                          {r.hubs && <div className="sub">Depuis {r.hubs}</div>}
                        </div>
                      </div>
                    </td>
                    <td className="num">
                      <div className="meter-cell">
                        <span>{r.score?.toFixed(1).replace(".", ",")}</span>
                        <span className="meter" aria-hidden="true">
                          <i style={{ width: `${Math.max(4, Math.min(100, r.score ?? 0))}%` }} />
                        </span>
                      </div>
                    </td>
                    <td className="num">{km(r.distance_km)}</td>
                    <td className="num">{int(r.pax_hubs)}</td>
                    <td className="num">
                      {r.croissance == null ? (
                        <span className="delta flat">n.d.</span>
                      ) : (
                        <span className={`delta ${r.croissance >= 0 ? "up" : "down"}`}>
                          {r.croissance >= 0 ? "▲" : "▼"} {signedPct(r.croissance)}
                        </span>
                      )}
                    </td>
                    <td className="num">
                      <div className="meter-cell">
                        <span className="strong">{meurFromM(r.resultat_meur)}</span>
                        <span className="meter alt" aria-hidden="true">
                          <i style={{ width: `${Math.max(4, (Math.max(0, r.resultat_meur) / maxResult) * 100)}%` }} />
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${verdictTone(r.verdict)}`}>{verdictShort(r.verdict)}</span>
                      <div className="sub" style={{ marginTop: 6 }}>
                        {r.alertes.length} objection{r.alertes.length > 1 ? "s" : ""}
                        {r.alertes[0] ? ` · ${ALERT_LABELS[r.alertes[0]] ?? r.alertes[0]}` : ""}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="muted small" style={{ marginTop: 20 }}>
            Pourquoi presque tous les dossiers concluent « approfondir avant décision » : les données publiques ne
            mesurent pas la demande réelle entre Paris et chaque destination, et la recette utilisée est une moyenne
            du réseau. CAP le signale honnêtement plutôt que de recommander une ouverture sur des bases fragiles. Sur
            les données internes d'une compagnie, ces réserves tombent.
          </p>
        </div>
      </section>
    </>
  );
}
