import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import Link from "next/link";
import { AgentChat } from "@/components/AgentChat";
import { CAP_API } from "@/lib/data";

export const metadata: Metadata = { title: "Agents IA · CAP" };

function examples(): { id: string; question: string; ok: boolean }[] {
  const file = path.join(process.cwd(), "data", "analyste", "index.json");
  if (!fs.existsSync(file)) return [];
  return (JSON.parse(fs.readFileSync(file, "utf-8")) as { id: string; question: string; ok: boolean }[]).filter((x) => x.ok);
}

const TOOLS = [
  ["Chercher dans le radar", "Destinations que Paris ne dessert pas, filtrées par segment, région, pays ou distance."],
  ["Étude de marché", "Trafic de Paris et des 16 hubs vers une destination, part et rang de Paris, évolution, santé de la ligne."],
  ["Simuler la ligne", "Compte de résultat avec la fréquence, l'appareil, le remplissage, le prix des billets, le carburant et la saison choisis."],
  ["Sensibilités", "Les hypothèses qui font le plus varier le résultat d'une ligne."],
];

export default function AgentsPage() {
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <p className="eyebrow">Agents IA</p>
          <h1 style={{ fontSize: "clamp(38px, 5vw, 60px)" }}>Deux agents qui décident eux-mêmes de ce qu'ils vérifient</h1>
          <p className="lead">
            Posez une question d'ouverture de ligne. L'Analyste choisit ses outils, lit les résultats, creuse quand un
            chiffre l'interpelle, puis répond. Le Contradicteur vérifie à son tour et peut le renvoyer à sa copie.
            Tout leur raisonnement s'affiche en direct.
          </p>
        </div>
      </section>

      <section className="section tight">
        <div className="wrap">
          <AgentChat api={CAP_API} examples={examples()} />
        </div>
      </section>

      <section className="section paper">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Ce qui en fait des agents</p>
            <h2>Une boucle de décision, pas un ordre fixe</h2>
            <p className="lead">
              À chaque tour, le modèle de langage reçoit la question, ce qu'il a déjà appris et la liste des outils. Il
              décide seul : appeler un outil (lequel, avec quels paramètres) ou répondre. Deux questions différentes
              donnent deux parcours différents.
            </p>
          </div>
          <div className="grid g4">
            <div className="card"><span className="num">01 · Décider</span><p>L'agent annonce ce qu'il veut vérifier et pourquoi.</p></div>
            <div className="card"><span className="num">02 · Agir</span><p>Il appelle un outil : une requête BigQuery ou le modèle économique, jamais du SQL écrit par lui.</p></div>
            <div className="card"><span className="num">03 · Observer</span><p>Il lit le résultat. Une marge fine, une demande sur un seul hub ? Il approfondit.</p></div>
            <div className="card accent"><span className="num">04 · Conclure</span><p>Quand il en sait assez, il répond. Le garde-fou contrôle, le Contradicteur conteste.</p></div>
          </div>

          <div className="explain" style={{ marginTop: 48 }}>
            <div>
              <h3 style={{ marginBottom: 14 }}>Les outils à leur disposition</h3>
              <dl className="glossary">
                {TOOLS.map(([n, d]) => <div key={n}><dt>{n}</dt><dd>{d}</dd></div>)}
              </dl>
            </div>
            <div className="table-box">
              <table style={{ minWidth: 520 }}>
                <thead><tr><th></th><th>Chaîne d'instruction</th><th>Agents IA</th></tr></thead>
                <tbody>
                  <tr><td className="dest-name">Sert à</td><td className="sub">Produire les dossiers d'ouverture</td><td className="sub">Répondre aux questions ouvertes</td></tr>
                  <tr><td className="dest-name">Parcours</td><td className="sub">Fixe, six étapes</td><td className="sub">Choisi par l'IA à chaque tour</td></tr>
                  <tr><td className="dest-name">Rôle de l'IA</td><td className="sub">Rédiger la note</td><td className="sub">Choisir les outils, raisonner, rédiger, contester</td></tr>
                  <tr><td className="dest-name">Reproductible</td><td className="sub">Oui, à l'identique</td><td className="sub">Non, mais chaque chiffre est tracé</td></tr>
                  <tr><td className="dest-name">Garde-fou</td><td className="sub">Oui</td><td className="sub">Oui</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="callout" style={{ marginTop: 32 }}>
            <p>
              <b>Pourquoi deux mécanismes ?</b> Un business plan doit donner le même résultat à chaque fois : il suit
              une chaîne fixe. Une question ouverte demande d'explorer : le chemin dépend de ce qu'on découvre. Dans les
              deux cas, l'IA ne fabrique aucun chiffre : elle cite les références renvoyées par les outils, et le code
              insère les valeurs.
            </p>
          </div>
          <div className="actions" style={{ marginTop: 28 }}>
            <Link className="btn line" href="/radar">Voir les dossiers de la chaîne d'instruction</Link>
            <Link className="btn line" href="/gcp">Voir l'infrastructure GCP</Link>
          </div>
        </div>
      </section>
    </>
  );
}
