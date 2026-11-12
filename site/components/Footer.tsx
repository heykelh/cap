import Link from "next/link";
import { getMeta } from "@/lib/data";
import { day } from "@/lib/format";
import { MEDIA } from "@/lib/media";

export function Footer() {
  const meta = getMeta();
  return (
    <footer>
      <div className="wrap">
        <p style={{ margin: 0, color: "#fff", fontWeight: 600 }}>CAP · Projet de Heykel Hachiche</p>
        <p style={{ margin: 0 }}>
          Projet indépendant, conçu comme démonstration pour une équipe de planification réseau. Il n'est ni affilié
          à Air France ni validé par la compagnie. Les données sont publiques : Eurostat, OurAirports et le
          communiqué annuel d'Air France-KLM.
        </p>
        <p style={{ margin: 0 }}>
          Dossiers générés le {day(meta.genere_le)} · Code source :{" "}
          <a href="https://github.com/heykelh">github.com/heykelh</a> ·{" "}
          <Link href="/methode#limites">Limites et transparence</Link>
          {MEDIA.credit ? ` · ${MEDIA.credit}` : ""}
        </p>
      </div>
    </footer>
  );
}
