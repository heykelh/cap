import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { InstructionRun } from "@/components/InstructionRun";
import { Simulator } from "@/components/Simulator";
import { CAP_API, getDossier, getMeta, getRadar } from "@/lib/data";
import { ALERT_LABELS, km, verdictShort, verdictTone } from "@/lib/format";

export function generateStaticParams() {
  return getRadar().map((r) => ({ iata: r.iata }));
}

type Params = { params: Promise<{ iata: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { iata } = await params;
  const d = getDossier(iata);
  return { title: `Dossier Paris CDG vers ${d?.opportunity?.partner_city ?? iata} · CAP` };
}

const GRAVITY = { haute: "stop", moyenne: "watch", basse: "tpl" } as const;

export default async function DossierPage({ params }: Params) {
  const { iata } = await params;
  const d = getDossier(iata);
  if (!d) notFound();
  const meta = getMeta();
  const opp = d.opportunity ?? {};
  const city = opp.partner_city ?? d.destination;
  const h = meta.hypotheses;

  // La note est affichée sans son annexe, qui est présentée sous forme de tableau plus bas.
  const [noteBody] = d.note_markdown.split(/\n-{3,}\n+## Annexe/);
  const writer = d.journal.find((j) => j.agent === "Rédacteur");
  const byAi = writer?.statut.startsWith("rédigé par le LLM");
  const facts = Object.entries(d.faits).filter(([k]) => !k.startsWith("alerte") && k !== "verdict");

  return (
    <>
      <section className="dossier-head">
        <div className="wrap">
          <p className="eyebrow"><Link href="/radar" style={{ color: "inherit" }}>Radar</Link> · Dossier d'ouverture</p>
          <h1 style={{ fontSize: "clamp(36px, 5vw, 58px)" }}>Paris CDG vers {city} <span className="mono" style={{ fontSize: "0.45em", color: "#9fb0c9" }}>{d.destination}</span></h1>
          <p className="lead" style={{ margin: 0 }}>
            {km(opp.distance_from_cdg_km)} · scénario de départ : {d.scenario.freq} allers-retours par semaine en{" "}
            {d.scenario.aircraft} · remplissage de référence : {d.scenario.region ?? "moyenne long-courrier"}
          </p>
          <div><span className={`badge ${verdictTone(d.verdict)}`}>Recommandation : {verdictShort(d.verdict)}</span></div>
        </div>
      </section>

      <section className="section tight">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Simuler</p>
            <h2>Modifiez les hypothèses, le résultat se recalcule</h2>
            <p className="lead">
              C'est ici que l'analyste exerce son jugement : fréquence, appareil, remplissage, prix des billets,
              carburant, saisonnalité. Les hypothèses de départ viennent du communiqué annuel 2025 d'Air France-KLM.
            </p>
          </div>
          <Simulator
            distanceKm={Number(opp.distance_from_cdg_km)}
            marketPax={opp.pax_l12_hubs ? Number(opp.pax_l12_hubs) : null}
            defaults={{
              freq: d.scenario.freq,
              aircraft: d.scenario.aircraft,
              loadFactor: (d.scenario.region && h.remplissage_par_region[d.scenario.region]) || h.valeurs.load_factor.valeur,
              weeks: h.valeurs.weeks_per_year.valeur,
            }}
            assumptions={{
              yield: h.valeurs.yield_eur_per_rpk.valeur,
              cask: h.valeurs.cost_eur_per_ask.valeur,
              fuel: h.valeurs.fuel_eur_per_ask.valeur,
            }}
            aircraft={h.appareils}
          />
        </div>
      </section>

      <section className="section tight">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">La note</p>
            <h2>La note d'ouverture</h2>
            <p className="lead">
              {byAi
                ? "Rédigée par l'intelligence artificielle, puis vérifiée automatiquement : aucun chiffre n'a été écrit par l'IA, tous viennent du calcul."
                : "Rédigée à partir de gabarits contrôlés : l'IA n'était pas disponible au moment de la génération, la note a été produite par le plan de secours."}{" "}
              Elle correspond au scénario de départ.
            </p>
          </div>
          <article className="note">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{noteBody}</ReactMarkdown>
          </article>
        </div>
      </section>

      <section className="section tight">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Les coulisses</p>
            <h2>Revoir la chaîne d'instruction de ce dossier</h2>
            <p className="lead">L'enregistrement réel : chaque requête BigQuery, chaque fait calculé, chaque brouillon de l'IA.</p>
          </div>
          <InstructionRun api={CAP_API} dossiers={[{ iata: d.destination, ville: city }]} initialDest={d.destination} compact />
        </div>
      </section>

      <section className="section tight">
        <div className="wrap explain">
          <div>
            <div className="section-head" style={{ marginBottom: 24 }}>
              <p className="eyebrow">Avocat du diable</p>
              <h2>Les objections</h2>
              <p className="muted">Déclenchées par des règles explicites, pas par l'IA.</p>
            </div>
            <ul className="alert-list">
              {d.alertes.map((a, i) => (
                <li key={a.code}>
                  <span className={`badge ${GRAVITY[a.gravite]}`}>{a.gravite}</span>
                  <div>
                    <b>{ALERT_LABELS[a.code] ?? a.code}</b>
                    <p>{d.faits[`alerte${i + 1}`]?.valeur ?? a.texte}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="section-head" style={{ marginBottom: 24 }}>
              <p className="eyebrow">Traçabilité</p>
              <h2>Le journal des étapes</h2>
              <p className="muted">Qui a fait quoi, et avec quel outil.</p>
            </div>
            <div className="journal">
              {d.journal.map((j, i) => (
                <div key={i}>
                  <b>{j.agent}</b>
                  <span className="muted">
                    {j.statut === "ok" ? `données chargées depuis ${j.source}` : j.statut}
                    {j.statut.startsWith("rédigé") && j.llm ? ` (${j.llm})` : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="section tight">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Annexe</p>
            <h2>Chaque chiffre et sa source</h2>
          </div>
          <div className="table-box">
            <table>
              <thead><tr><th>Indicateur</th><th className="num">Valeur</th><th>Source</th></tr></thead>
              <tbody>
                {facts.map(([k, f]) => (
                  <tr key={k}><td>{f.libelle}</td><td className="num">{f.valeur}</td><td className="small muted">{f.source}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="callout" style={{ marginTop: 28 }}>
            <p><b>Limites connues.</b> {d.limites.join(" ")}</p>
          </div>
          <div className="actions" style={{ marginTop: 28 }}>
            <Link className="btn line" href="/radar">Retour au radar</Link>
            <Link className="btn line" href="/methode">Comprendre la méthode</Link>
          </div>
        </div>
      </section>
    </>
  );
}
