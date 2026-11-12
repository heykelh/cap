import Link from "next/link";
import type { Metadata } from "next";
import { getMeta } from "@/lib/data";
import { month } from "@/lib/format";
import { TECHNOLOGIES } from "@/lib/story";

export const metadata: Metadata = { title: "Comment ça marche · CAP" };

export default function MethodePage() {
  const meta = getMeta();
  const h = meta.hypotheses;
  const v = h.valeurs;
  const fr = meta.fraicheur_par_pays.find((f) => f.rep_country === "FR")?.last_month;
  const groups = Array.from(new Set(TECHNOLOGIES.map((t) => t.group)));

  return (
    <>
      <section className="hero">
        <div className="wrap">
          <p className="eyebrow">Comment ça marche</p>
          <h1 style={{ fontSize: "clamp(38px, 5vw, 60px)" }}>De la donnée brute à la recommandation</h1>
          <p className="lead">
            Cette page explique tout le fonctionnement de CAP, sans prérequis technique : d'où viennent les
            données, comment elles sont nettoyées, comment la rentabilité est calculée, comment travaillent les
            étapes d'instruction et les agents IA, et ce que l'outil ne sait pas faire.
          </p>
          <nav aria-label="Sommaire" className="actions">
            {[["#chaine", "La chaîne"], ["#donnees", "Les données"], ["#score", "Le score"], ["#modele", "Le modèle"],
              ["#garde-fou", "Le garde-fou"], ["#technologies", "Les technologies"], ["#limites", "Les limites"]].map(([href, label]) => (
              <a key={href} className="btn ghost" href={href} style={{ minHeight: 40, fontSize: 15 }}>{label}</a>
            ))}
          </nav>
        </div>
      </section>

      {/* Chaîne */}
      <section className="section dark" id="chaine">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Vue d'ensemble</p>
            <h2>Huit étapes, de la source au dossier, chaque mois</h2>
            <p className="lead">Chaque étape ne fait qu'une chose, et peut être vérifiée indépendamment des autres.</p>
          </div>
          <ol className="pipeline">
            <li><b>Collecter</b><span>Téléchargement automatique du trafic aérien Eurostat et du référentiel des aéroports.</span></li>
            <li><b>Stocker brut</b><span>Les données sont rangées telles quelles dans BigQuery, avec leur date et leur adresse d'origine.</span></li>
            <li><b>Nettoyer</b><span>Une ligne par route et par mois, codes harmonisés, distances calculées, anomalies signalées.</span></li>
            <li><b>Analyser</b><span>Fenêtres de douze mois, croissance, remplissage, santé des lignes, radar des opportunités.</span></li>
            <li><b>Chiffrer</b><span>Le modèle économique calcule le compte de résultat de la ligne étudiée.</span></li>
            <li><b>Instruire</b><span>Six étapes assemblent le dossier, l'avocat du diable formule les objections.</span></li>
            <li><b>Contrôler</b><span>Un garde-fou vérifie la note avant publication, et un plan de secours garantit un résultat.</span></li>
            <li><b>Recommencer</b><span>Chaque mois, Cloud Scheduler relance toute la chaîne et le site se met à jour.</span></li>
          </ol>
        </div>
      </section>

      {/* Données */}
      <section className="section" id="donnees">
        <div className="wrap explain">
          <div className="section-head" style={{ marginBottom: 0 }}>
            <p className="eyebrow">Les données</p>
            <h2>Trois couches, comme une raffinerie</h2>
            <p className="lead">
              Les données passent par trois couches successives dans l'entrepôt Google BigQuery. On parle
              d'architecture « médaillon » : bronze, argent, or.
            </p>
            <div className="callout">
              <p>
                Une donnée absente n'est pas une donnée nulle. Quand Eurostat masque un volume pour raison de
                confidentialité, CAP conserve la ligne et la signale. C'est ce qui a permis de corriger de faux
                positifs comme Dubaï ou Atlanta, présentés à tort comme non desservis depuis Paris.
              </p>
            </div>
          </div>
          <div className="grid">
            <div className="card"><span className="num">Bronze · brut</span><h3>1 439 824 lignes</h3><p>Passagers, sièges offerts et vols, par paire d'aéroports et par mois, déclarés par 33 pays européens depuis 2019. Rien n'est modifié : on garde une copie fidèle de la source.</p></div>
            <div className="card"><span className="num">Argent · nettoyé</span><h3>481 660 routes-mois</h3><p>Les trois mesures réunies sur une seule ligne, les villes et les distances ajoutées, chaque ligne étiquetée selon sa qualité : correcte, masquée, aéroport inconnu, incohérente.</p></div>
            <div className="card accent"><span className="num">Or · prêt à l'emploi</span><h3>Radar et santé des lignes</h3><p>Les indicateurs utilisés par la chaîne d'instruction et les agents IA. Aucun d'eux n'écrit jamais de requête eux-mêmes : ils appellent des requêtes écrites et relues à l'avance.</p></div>
          </div>
        </div>
      </section>

      {/* Score */}
      <section className="section paper" id="score">
        <div className="wrap explain">
          <div className="section-head" style={{ marginBottom: 0 }}>
            <p className="eyebrow">Le radar</p>
            <h2>Un score simple, que l'on peut expliquer</h2>
            <p className="lead">
              Le radar observe seize grands aéroports européens. Une destination y entre si au moins l'un d'eux la
              dessert régulièrement (au moins un vol par semaine en moyenne) et si Paris ne la dessert pas.
            </p>
          </div>
          <div className="table-box">
            <table>
              <thead><tr><th>Critère</th><th className="num">Poids</th><th>Ce qu'il mesure</th></tr></thead>
              <tbody>
                <tr><td>Volume</td><td className="num">40 %</td><td>Passagers transportés par les hubs concurrents vers la destination sur douze mois.</td></tr>
                <tr><td>Croissance</td><td className="num">25 %</td><td>Évolution de ce trafic par rapport aux douze mois précédents.</td></tr>
                <tr><td>Remplissage</td><td className="num">20 %</td><td>Part des sièges occupés sur ces vols : un indice de demande non servie.</td></tr>
                <tr><td>Nombre de hubs</td><td className="num">15 %</td><td>Plus il y a de hubs qui desservent la destination, moins la demande dépend d'un seul acteur.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Modèle */}
      <section className="section" id="modele">
        <div className="wrap explain">
          <div className="section-head" style={{ marginBottom: 0 }}>
            <p className="eyebrow">Le modèle économique</p>
            <h2>Le compte de résultat d'une ligne, en cinq lignes</h2>
            <p className="lead">
              Le calcul est volontairement lisible : toute personne peut le refaire à la main. Les hypothèses
              viennent du communiqué annuel 2025 d'Air France-KLM, page citée, et sont toutes modifiables dans le
              simulateur de chaque dossier.
            </p>
          </div>
          <div className="grid">
            <div className="card">
              <p className="mono" style={{ color: "var(--ink)", lineHeight: 1.9 }}>
                vols = 2 × fréquences × semaines<br />
                passagers = vols × sièges × remplissage<br />
                recette = passagers-km × recette par passager-km<br />
                coûts = sièges-km × coût par siège-km<br />
                résultat = recette − coûts
              </p>
            </div>
            <div className="table-box">
              <table>
                <thead><tr><th>Hypothèse</th><th className="num">Valeur</th><th>Source</th></tr></thead>
                <tbody>
                  {Object.entries(v).map(([k, a]) => (
                    <tr key={k}>
                      <td>{a.libelle}</td>
                      <td className="num">
                        {a.unite.startsWith("€") ? `${(a.valeur * 100).toFixed(2).replace(".", ",")} c€` :
                          a.unite.startsWith("part") ? `${(a.valeur * 100).toFixed(1).replace(".", ",")} %` : a.valeur}
                      </td>
                      <td className="small muted">{a.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      {/* Garde-fou */}
      <section className="section dark" id="garde-fou">
        <div className="wrap explain">
          <div className="section-head" style={{ marginBottom: 0 }}>
            <p className="eyebrow">Le garde-fou</p>
            <h2>L'intelligence artificielle rédige, le code calcule</h2>
            <p className="lead">
              Une IA de langage peut inventer un chiffre avec aplomb. Dans un dossier qui engage des millions
              d'euros, c'est inacceptable. CAP l'empêche par construction.
            </p>
          </div>
          <div className="grid">
            <div className="card">
              <span className="num">1 · L'IA reçoit des repères, pas des chiffres</span>
              <p>On lui fournit une liste de repères comme <span className="mono">{"{{resultat_meur}}"}</span> (résultat annuel) ou <span className="mono">{"{{remplissage_equilibre}}"}</span>, avec leur signification. Jamais leur valeur.</p>
            </div>
            <div className="card">
              <span className="num">2 · Un contrôle relit chaque texte</span>
              <p>Tout chiffre écrit par l'IA, tout repère inventé ou tout titre manquant entraîne un rejet. L'IA reçoit le motif et réécrit, deux fois au maximum.</p>
            </div>
            <div className="card">
              <span className="num">3 · Le code remplace les repères</span>
              <p>Les valeurs calculées sont insérées à la fin. Si l'IA échoue ou ne répond pas, une note de secours rédigée à partir de gabarits contrôlés prend le relais.</p>
            </div>
            <div className="callout">
              <p>
                Test réel : une IA programmée pour écrire « la ligne rapportera 42 M€ avec un remplissage de 95 % »
                est rejetée à chaque tentative, et ces chiffres n'apparaissent jamais dans le dossier.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Fiabilité */}
      <section className="section paper">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Fiabilité</p>
            <h2>Conçu pour ne jamais bloquer</h2>
          </div>
          <div className="grid g3">
            <div className="card"><h3>Délai maximal</h3><p>Chaque appel à l'IA est interrompu au-delà d'un délai fixé. Pas d'attente sans fin.</p></div>
            <div className="card"><h3>Disjoncteur et relais</h3><p>Si un fournisseur d'IA est saturé, CAP passe au suivant (Groq, puis Gemini), puis à la note de secours.</p></div>
            <div className="card"><h3>Direct, avec secours</h3><p>Le site interroge l'API Cloud Run en direct. Si elle ne répond pas, il bascule sur les données exportées du dernier rafraîchissement.</p></div>
          </div>
        </div>
      </section>

      {/* Technologies */}
      <section className="section" id="technologies">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Les technologies</p>
            <h2>Ce qui a servi à construire CAP, et pourquoi</h2>
          </div>
          <div className="grid g2">
            {groups.map((g) => (
              <div className="card" key={g}>
                <span className="num">{g}</span>
                <dl className="glossary stack" style={{ borderTop: "none" }}>
                  {TECHNOLOGIES.filter((t) => t.group === g).map((t) => (
                    <div key={t.name}><dt>{t.name}</dt><dd>{t.role}</dd></div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
          <div className="callout" style={{ marginTop: 28 }}>
            <p>
              <b>Branchable sur des données internes.</b> Toute la lecture des données passe par une seule couche
              d'accès. Dans une compagnie, on remplace la source publique par ses propres tables (réservations,
              programme de vols, coûts réels) sans modifier la chaîne, les agents, le modèle ni ce site.
            </p>
          </div>
        </div>
      </section>

      {/* Limites */}
      <section className="section paper" id="limites">
        <div className="wrap explain">
          <div className="section-head" style={{ marginBottom: 0 }}>
            <p className="eyebrow">Transparence</p>
            <h2>Ce que CAP mesure, et ce qu'il approxime</h2>
            <p className="lead">Un outil d'aide à la décision doit dire ce qu'il ne sait pas.</p>
          </div>
          <div className="grid">
            <div className="card"><span className="num" style={{ color: "var(--green)" }}>Mesuré</span><p>Passagers, sièges et vols par paire d'aéroports et par mois. Distances. Présence des hubs concurrents. Données France publiées jusqu'à {month(fr)}.</p></div>
            <div className="card"><span className="num">Approximé</span><p>La demande réelle entre Paris et une destination finale n'est pas publique : CAP l'approche par le trafic des hubs concurrents. Les compagnies disposent de cette donnée en interne.</p></div>
            {h.limites.map((l) => (
              <div className="card" key={l}><span className="num">Limite</span><p>{l}</p></div>
            ))}
          </div>
        </div>
      </section>

      <section className="section tight">
        <div className="wrap actions">
          <Link className="btn primary" href="/radar">Voir le radar</Link>
          <Link className="btn line" href="/chronologie">Voir la chronologie du projet</Link>
        </div>
      </section>
    </>
  );
}
