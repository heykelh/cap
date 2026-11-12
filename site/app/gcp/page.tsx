import type { Metadata } from "next";
import { ApiStatus } from "@/components/ApiStatus";
import { SqlViewer } from "@/components/SqlViewer";
import { CAP_API, getGcp } from "@/lib/data";
import { day } from "@/lib/format";

export const metadata: Metadata = { title: "Sous le capot : Google Cloud · CAP" };

const nf = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
function size(b: number) {
  if (b >= 1e9) return `${(b / 1e9).toFixed(2).replace(".", ",")} Go`;
  if (b >= 1e6) return `${(b / 1e6).toFixed(1).replace(".", ",")} Mo`;
  return `${(b / 1e3).toFixed(0)} Ko`;
}
function duration(s: number) {
  return s >= 60 ? `${Math.floor(s / 60)} min ${Math.round(s % 60)} s` : `${s.toFixed(1).replace(".", ",")} s`;
}

const REFRESH_LANE = [
  { k: "Cloud Scheduler", t: "Le déclencheur", d: "Chaque mois, le 5 à 6 h (heure de Paris), lance le rafraîchissement." },
  { k: "Cloud Run Job", t: "cap-refresh", d: "Télécharge Eurostat et OurAirports, exécute le SQL, instruit les dossiers, exporte les études." },
  { k: "BigQuery", t: "bronze → silver → gold", d: "L'entrepôt : données brutes, nettoyées, puis indicateurs prêts à l'emploi." },
  { k: "Cloud Storage", t: "paquet de données", d: "Dossiers, études et inventaire publiés en un fichier, lu par le site." },
  { k: "Vercel", t: "site reconstruit", d: "Un crochet de déploiement reconstruit le site avec les données du mois." },
];
const LIVE_LANE = [
  { k: "Visiteur", t: "ce site", d: "Tape une destination ou lance une instruction en direct." },
  { k: "Cloud Run", t: "cap-api", d: "API Python (FastAPI) : étude de marché, chaîne d'instruction et agents IA, à la demande." },
  { k: "BigQuery", t: "requêtes paramétrées", d: "Lecture des tables gold et silver, quelques mégaoctets par requête." },
  { k: "Secret Manager", t: "clés de l'IA", d: "Les clés Groq et Gemini ne sont jamais dans le code." },
  { k: "Groq / Gemini", t: "agents IA", d: "L'Analyste et le Contradicteur choisissent leurs outils ; le garde-fou contrôle." },
];

function Lane({ title, nodes }: { title: string; nodes: typeof REFRESH_LANE }) {
  return (
    <div className="lane">
      <p className="lane-title">{title}</p>
      <ol className="lane-nodes">
        {nodes.map((n) => (
          <li key={n.k + n.t} className="node">
            <span className="node-k">{n.k}</span>
            <b>{n.t}</b>
            <p>{n.d}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function GcpPage() {
  const g = getGcp();
  const r = g?.dernier_rafraichissement;
  const tables = g?.datasets.flatMap((d) => d.tables) ?? [];
  const totalRows = tables.reduce((a, t) => a + (t.lignes || 0), 0);
  const totalBytes = tables.reduce((a, t) => a + (t.octets || 0), 0);
  const jobs = g?.requetes_30_jours;

  return (
    <>
      <section className="hero">
        <div className="wrap">
          <p className="eyebrow">Sous le capot</p>
          <h1 style={{ fontSize: "clamp(38px, 5vw, 60px)" }}>Ce qui tourne réellement sur Google Cloud</h1>
          <p className="lead">
            Un entrepôt BigQuery mis à jour chaque mois sans intervention, une API sur Cloud Run qui interroge cet
            entrepôt à la demande, et deux agents IA qui s'en servent comme d'outils. Tout ce qui suit est lu dans le projet GCP
            {g ? ` « ${g.projet} »` : ""}, pas décrit de mémoire.
          </p>
          {g && (
            <div className="hero-badges">
              <span>{tables.length} tables BigQuery</span>
              <span>{nf.format(totalRows)} lignes</span>
              <span>{size(totalBytes)} stockés</span>
              <span>Région {g.localisation}</span>
            </div>
          )}
        </div>
      </section>

      <section className="section dark">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Architecture</p>
            <h2>Deux circuits : le rafraîchissement mensuel et le direct</h2>
            <p className="lead">
              Le premier tourne seul une fois par mois. Le second s'active quand quelqu'un utilise le site. Une même
              image Docker sert aux deux.
            </p>
          </div>
          <Lane title="Circuit 1 · Rafraîchissement automatique, chaque mois" nodes={REFRESH_LANE} />
          <Lane title="Circuit 2 · Direct, à chaque demande" nodes={LIVE_LANE} />
        </div>
      </section>

      <section className="section">
        <div className="wrap explain">
          <div className="section-head" style={{ marginBottom: 0 }}>
            <p className="eyebrow">Mise à jour</p>
            <h2>Tous les mois, sans intervention</h2>
            <p className="lead">
              Eurostat publie le trafic aérien avec quelques mois de décalage selon les pays. Un rafraîchissement mensuel
              suffit : chaque mois, CAP recharge les sources, recalcule les trois couches, refait instruire tous les
              dossiers long-courrier et republie le site.
            </p>
            <div className="callout">
              <p>
                Si une étape échoue, rien n'est publié : le site garde les données du mois précédent, et le journal
                ci-contre indique l'étape en cause.
              </p>
            </div>
          </div>
          <div className="panel-dark">
            <h3>Dernier rafraîchissement</h3>
            {r ? (
              <>
                <p className="muted-d">
                  {day(r.debut)} · {r.declencheur} · <b className={r.statut === "réussi" ? "ok-txt" : "bad-txt"}>{r.statut}</b>
                </p>
                <ol className="steps">
                  {r.etapes.map((e) => (
                    <li key={e.etape} className={e.statut === "ok" ? "ok" : "ko"}>
                      <span className="step-layer">{e.couche}</span>
                      <span className="step-name">{e.etape}{e.resume ? <small>{e.resume}</small> : null}</span>
                      <span className="step-dur">{duration(e.duree_s)}</span>
                    </li>
                  ))}
                </ol>
                {r.publication && <p className="muted-d">{r.publication}</p>}
              </>
            ) : (
              <p className="muted-d">Aucun rafraîchissement automatique enregistré pour l'instant.</p>
            )}
          </div>
        </div>
      </section>

      {g && (
        <section className="section paper">
          <div className="wrap">
            <div className="section-head">
              <p className="eyebrow">BigQuery</p>
              <h2>L'entrepôt, table par table</h2>
              <p className="lead">Inventaire lu dans BigQuery le {day(g.genere_le)}.</p>
            </div>
            <div className="grid">
              {g.datasets.map((d) => (
                <div key={d.dataset}>
                  <p className="dataset-title"><span className="code">{d.dataset}</span> {d.role}</p>
                  <div className="table-box">
                    <table style={{ minWidth: 640 }}>
                      <thead><tr><th>Table</th><th className="num">Lignes</th><th className="num">Taille</th><th className="num">Colonnes</th><th className="num">Mise à jour</th></tr></thead>
                      <tbody>
                        {d.tables.map((t) => (
                          <tr key={t.table}>
                            <td className="dest-name">{t.table}</td>
                            <td className="num">{nf.format(t.lignes)}</td>
                            <td className="num">{size(t.octets)}</td>
                            <td className="num">{t.colonnes}</td>
                            <td className="num">{t.modifiee_le ? day(t.modifiee_le) : "n.d."}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
            {jobs && !jobs.erreur && (
              <div className="kpis" style={{ marginTop: 28 }}>
                <div className="kpi"><span>Requêtes sur 30 jours</span><b>{nf.format(jobs.requetes ?? 0)}</b></div>
                <div className="kpi"><span>Données lues sur 30 jours</span><b>{size(jobs.octets_lus ?? 0)}</b></div>
                <div className="kpi"><span>Servies depuis le cache</span><b>{nf.format(jobs.en_cache ?? 0)}</b></div>
                <div className="kpi hl"><span>Temps de calcul</span><b>{nf.format((jobs.slot_ms ?? 0) / 1000)} s</b></div>
              </div>
            )}
          </div>
        </section>
      )}

      {g && g.sql.length > 0 && (
        <section className="section">
          <div className="wrap">
            <div className="section-head">
              <p className="eyebrow">Transformations</p>
              <h2>Le SQL exécuté par BigQuery</h2>
              <p className="lead">
                Chaque fichier produit une table. Ni la chaîne d'instruction ni les agents IA n'écrivent de SQL : ils
                appellent des requêtes paramétrées, affichées en direct sur le site.
              </p>
            </div>
            <SqlViewer files={g.sql} />
          </div>
        </section>
      )}

      <section className="section dark">
        <div className="wrap explain">
          <div className="section-head" style={{ marginBottom: 0 }}>
            <p className="eyebrow">Preuve en direct</p>
            <h2>Interrogez l'API maintenant</h2>
            <p className="lead">
              Ce bouton appelle le service Cloud Run, qui exécute une requête sur BigQuery et renvoie l'identifiant du
              job. Rien n'est simulé.
            </p>
          </div>
          <div className="panel-dark" style={{ background: "rgba(255,255,255,.03)" }}>
            <ApiStatus api={CAP_API} />
          </div>
        </div>
      </section>

      <section className="section paper">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Exploitation</p>
            <h2>Sécurité, fiabilité, coûts</h2>
          </div>
          <div className="grid g3">
            <div className="card"><h3>Compte de service dédié</h3><p>L'API et le job tournent sous une identité qui ne peut que lire et écrire les tables CAP, lancer des requêtes et lire ses deux secrets.</p></div>
            <div className="card"><h3>Secrets hors du code</h3><p>Les clés d'IA sont stockées dans Secret Manager et injectées au démarrage. Le dépôt GitHub n'en contient aucune.</p></div>
            <div className="card"><h3>Limites de sécurité</h3><p>Huit demandes par visiteur toutes les dix minutes, deux instances au plus, délai maximal par appel : la facture ne peut pas s'emballer.</p></div>
            <div className="card"><h3>Toujours une réponse</h3><p>Si l'API ne répond pas, le site bascule sur les données exportées du mois. La démonstration ne dépend d'aucun service unique.</p></div>
            <div className="card"><h3>Facturation à l'usage</h3><p>Cloud Run s'arrête quand personne ne s'en sert. Une alerte de budget prévient au moindre dépassement.</p></div>
            <div className="card accent"><h3>Branchable en interne</h3><p>Pour une compagnie, il suffit de pointer la couche d'accès vers ses propres tables BigQuery : réservations, programme de vols, coûts réels.</p></div>
          </div>
        </div>
      </section>
    </>
  );
}
