import type { Metadata } from "next";
import { MarketStudy } from "@/components/MarketStudy";
import { CAP_API, getMeta } from "@/lib/data";

export const metadata: Metadata = { title: "Étude de marché · CAP" };

export default function MarchePage() {
  const h = getMeta().hypotheses;
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <p className="eyebrow">Usage 2 · Étudier un marché</p>
          <h1 style={{ fontSize: "clamp(38px, 5vw, 60px)" }}>Tapez une destination. CAP étudie son marché.</h1>
          <p className="lead">
            Que Paris la desserve ou non : trafic depuis Paris et depuis les 16 grands hubs européens, part de Paris,
            évolution mois par mois depuis 2019, remplissage, santé de la ligne ou place au radar, puis simulation
            du compte de résultat si Paris ouvrait la ligne.
          </p>
          <div className="hero-badges">
            <span>{CAP_API ? "Requêtes BigQuery en direct via Cloud Run" : "Données exportées de BigQuery"}</span>
            <span>Bascule automatique sur l'export si l'API ne répond pas</span>
            <span>Chaque requête affichée avec son coût</span>
          </div>
        </div>
      </section>
      <section className="section tight">
        <div className="wrap">
          <MarketStudy
            api={CAP_API}
            hypotheses={{
              yield: h.valeurs.yield_eur_per_rpk.valeur,
              cask: h.valeurs.cost_eur_per_ask.valeur,
              fuel: h.valeurs.fuel_eur_per_ask.valeur,
              loadFactor: h.valeurs.load_factor.valeur,
              weeks: h.valeurs.weeks_per_year.valeur,
              aircraft: h.appareils,
            }}
          />
        </div>
      </section>
    </>
  );
}
