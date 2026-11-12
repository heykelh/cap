import Link from "next/link";
import type { Metadata } from "next";
import { TIMELINE } from "@/lib/story";

export const metadata: Metadata = { title: "Chronologie du projet · CAP" };

export default function ChronologiePage() {
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <p className="eyebrow">Chronologie</p>
          <h1 style={{ fontSize: "clamp(38px, 5vw, 60px)" }}>Comment CAP a été construit</h1>
          <p className="lead">
            Trois semaines, du cadrage du besoin à la mise en ligne. Les obstacles sont racontés aussi : ce sont
            eux qui ont rendu l'outil fiable.
          </p>
        </div>
      </section>

      <section className="section">
        <div className="wrap">
          <ol className="timeline">
            {TIMELINE.map((m) => (
              <li key={`${m.date}-${m.title}`}>
                <div>
                  <span className="when">{m.date}</span>
                  <span className="phase">{m.phase}</span>
                </div>
                <h3>{m.title}</h3>
                <p>{m.text}</p>
                {m.lesson && <p className="lesson">Leçon retenue : {m.lesson}</p>}
              </li>
            ))}
          </ol>
          <div className="actions" style={{ marginTop: 16 }}>
            <Link className="btn primary" href="/radar">Voir le résultat : le radar</Link>
            <Link className="btn line" href="/methode">Comprendre la méthode</Link>
          </div>
        </div>
      </section>
    </>
  );
}
