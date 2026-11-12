import Link from "next/link";
import { WorldMap } from "@/components/WorldMap";
import { getMeta, getRadar } from "@/lib/data";
import { meurFromM, month, verdictShort } from "@/lib/format";
import { MEDIA, media } from "@/lib/media";
import { PROJECT_FIGURES } from "@/lib/story";

export default function Home() {
  const radar = getRadar();
  const meta = getMeta();
  const first = radar[0];
  const lastFr = meta.fraicheur_par_pays.find((f) => f.rep_country === "FR")?.last_month;

  return (
    <>
      {/* 1. Accroche */}
      <section className="hero">
        {MEDIA.heroVideo && (
          <video className="hero-video" autoPlay muted loop playsInline poster={media(MEDIA.heroPoster)} aria-hidden="true">
            <source src={media(MEDIA.heroVideo)} type="video/mp4" />
          </video>
        )}
        <div className="wrap hero-grid">
          <div>
            <p className="eyebrow">Aide à la décision pour la planification réseau</p>
            <h1>
              Faut-il ouvrir une nouvelle ligne au départ de Paris&nbsp;? <em>CAP</em> instruit le dossier en
              quelques secondes.
            </h1>
            <p className="lead">
              CAP repère les destinations que les grands aéroports européens desservent et que Paris ne dessert
              pas, puis prépare un dossier complet : taille du marché, concurrence, rentabilité, risques. Deux
              agents IA répondent aux questions ouvertes en interrogeant eux-mêmes les données. L'analyste garde
              la main sur chaque hypothèse et sur la décision.
            </p>
            <div className="actions">
              <Link className="btn primary" href="/marche">Étudier une destination</Link>
              <Link className="btn ghost" href="/agents">Interroger les agents IA</Link>
            </div>
          </div>
          <WorldMap rows={radar} title="Carte des destinations du radar reliées à Paris CDG" />
          <div className="hero-badges">
            <span>Données publiques officielles</span>
            <span>Entrepôt Google BigQuery</span>
            <span>Chaque chiffre relié à sa source</span>
            <span>L'IA rédige, le code calcule</span>
            <span>Rafraîchi chaque mois, automatiquement</span>
          </div>
        </div>
      </section>

      {/* 2. Chiffres */}
      <section className="section tight paper">
        <div className="wrap">
          <div className="grid g3">
            {PROJECT_FIGURES.map((f) => (
              <div className="figure" key={f.label}>
                <b>{f.value}</b>
                <span>{f.label}</span>
                <small>{f.note}</small>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3. Le métier */}
      <section className="section">
        <div className="wrap explain">
          <div className="section-head" style={{ marginBottom: 0 }}>
            <p className="eyebrow">Le métier en une minute</p>
            <h2>Une compagnie aérienne est un réseau, et chaque ligne est un pari</h2>
            <p className="lead">
              Une compagnie dispose d'un nombre limité d'avions. Chaque avion affecté à une nouvelle destination
              est un avion retiré ailleurs. L'équipe de planification réseau décide donc où voler, à quelle
              fréquence et avec quel appareil.
            </p>
            <div className="callout">
              <p>
                Ouvrir une ligne long-courrier engage des dizaines de millions d'euros par an. Avant de décider,
                un analyste doit réunir le trafic existant, la concurrence, une estimation de recette et de coûts,
                puis défendre son dossier devant la direction. Ce travail prend des jours.
              </p>
            </div>
          </div>
          <dl className="glossary" aria-label="Lexique">
            <div><dt>Hub</dt><dd>Grand aéroport où une compagnie concentre ses vols pour organiser les correspondances, comme Paris CDG, Amsterdam ou Francfort.</dd></div>
            <div><dt>Ligne directe</dt><dd>Vol sans escale entre deux villes. Sans ligne directe, le voyageur passe par un autre hub, souvent chez un concurrent.</dd></div>
            <div><dt>Remplissage</dt><dd>Part des sièges occupés par des passagers payants. Une ligne n'est rentable qu'au-dessus d'un certain remplissage, dit d'équilibre.</dd></div>
            <div><dt>Siège-kilomètre</dt><dd>Un siège transporté sur un kilomètre. C'est l'unité de base pour comparer les coûts de lignes de longueurs différentes.</dd></div>
            <div><dt>Recette par passager-km</dt><dd>Ce que rapporte en moyenne un passager pour chaque kilomètre parcouru. On l'appelle aussi « yield ».</dd></div>
          </dl>
        </div>
      </section>

      {/* 4. Le problème */}
      <section className="section paper">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Le besoin</p>
            <h2>Trois difficultés que CAP s'attaque à réduire</h2>
          </div>
          <div className="grid g3">
            <div className="card">
              <span className="num">01</span>
              <h3>Des données éparpillées</h3>
              <p>Trafic, concurrence, coûts et capacités viennent de sources différentes, aux formats et aux dates différents. Les rassembler prend du temps et introduit des erreurs.</p>
            </div>
            <div className="card">
              <span className="num">02</span>
              <h3>Des dossiers lents et difficiles à comparer</h3>
              <p>Chaque dossier est construit à la main. Comparer des dizaines de destinations avec la même méthode est presque impossible dans un délai raisonnable.</p>
            </div>
            <div className="card">
              <span className="num">03</span>
              <h3>Le risque de l'optimisme</h3>
              <p>Un dossier défendu par son auteur tend à minimiser les risques. Il manque souvent un contradicteur systématique qui pose les questions qui fâchent.</p>
            </div>
          </div>
        </div>
      </section>

      {/* 5. Ce que fait CAP */}
      <section className="section dark">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">La réponse</p>
            <h2>Ce que fait CAP, concrètement</h2>
            <p className="lead">Trois usages, qui correspondent aux trois temps du travail d'un analyste réseau.</p>
          </div>
          <div className="grid g3">
            <div className="card">
              <span className="num">Détecter</span>
              <h3>Le radar d'opportunités</h3>
              <p>CAP regarde où volent seize grands aéroports européens et repère les destinations régulièrement desservies depuis Amsterdam, Francfort ou Istanbul, mais pas depuis Paris. Il les classe par un score transparent.</p>
            </div>
            <div className="card">
              <span className="num">Instruire</span>
              <h3>Le dossier d'ouverture</h3>
              <p>Pour une destination, une chaîne de six étapes produit une note d'une page : marché, concurrence, compte de résultat, objections, recommandation. Les hypothèses restent modifiables et le résultat se recalcule aussitôt.</p>
            </div>
            <div className="card">
              <span className="num">Piloter</span>
              <h3>La santé des lignes existantes</h3>
              <p>CAP suit aussi les lignes déjà exploitées depuis CDG : évolution du trafic, du remplissage, de la capacité, avec une alerte quand une ligne se dégrade.</p>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Chaîne d'instruction et agents IA */}
      <section className="section">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Comment CAP travaille</p>
            <h2>Une chaîne pour les dossiers, des agents pour les questions</h2>
            <p className="lead">
              Deux mécanismes différents, chacun à sa place. Un dossier d'ouverture doit être reproductible : il suit
              une chaîne fixe. Une question ouverte demande d'explorer : elle est confiée à des agents IA qui
              décident eux-mêmes de ce qu'ils vont vérifier.
            </p>
          </div>
          <div className="grid g2">
            <div className="card">
              <span className="num">Workflow déterministe</span>
              <h3>La chaîne d'instruction, en six étapes</h3>
              <p>
                Éclaireur, marché, concurrence, économiste, avocat du diable, rédacteur : toujours dans cet ordre,
                avec des requêtes et des règles écrites à l'avance. Seul le rédacteur fait appel à l'IA, pour écrire.
                Même destination, même dossier : c'est ce qu'on attend d'un business plan.
              </p>
            </div>
            <div className="card accent">
              <span className="num">Agents IA</span>
              <h3>L'Analyste et le Contradicteur</h3>
              <p>
                Posez une question libre. L'Analyste choisit ses outils (radar, étude de marché, simulation,
                sensibilités), examine chaque résultat et creuse quand un chiffre l'interpelle. Le Contradicteur
                vérifie à son tour avec les mêmes outils et renvoie ses objections. Leur chemin change à chaque question.
              </p>
            </div>
          </div>
          <div className="callout" style={{ marginTop: 32 }}>
            <p>
              <b>La règle d'or, pour les deux : l'intelligence artificielle raisonne et rédige, le code calcule.</b>{" "}
              L'IA ne cite un chiffre que par la référence que lui a donnée un outil, et le programme la remplace par
              la valeur calculée. Un contrôle rejette tout texte qui contient un chiffre écrit par l'IA.{" "}
              <Link href="/methode#garde-fou">Voir comment.</Link>
            </p>
          </div>
        </div>
      </section>

      {MEDIA.bandPhoto && (
        <div className="photo-band" style={{ backgroundImage: `url(${media(MEDIA.bandPhoto)})` }} role="img" aria-label="Photographie d'aéroport">
          {MEDIA.credit && <span className="credit">{MEDIA.credit}</span>}
        </div>
      )}

      {/* 7. Exemple */}
      {first && (
        <section className="section paper">
          <div className="wrap explain">
            <div className="section-head" style={{ marginBottom: 0 }}>
              <p className="eyebrow">Un exemple réel</p>
              <h2>Paris vers {first.ville ?? first.iata}</h2>
              <p className="lead">
                Première destination du radar. Desservie aujourd'hui en direct depuis
                {first.hubs ? ` ${first.hubs}` : " d'autres hubs européens"}, mais pas depuis Paris.
              </p>
              <div className="actions">
                <Link className="btn primary" href={`/dossier/${first.iata}`}>Lire le dossier complet</Link>
                <Link className="btn line" href="/radar">Comparer avec les autres</Link>
              </div>
            </div>
            <div className="grid g2">
              <div className="kpi"><span>Score d'opportunité</span><b>{first.score?.toFixed(1).replace(".", ",")} / 100</b></div>
              <div className="kpi"><span>Résultat annuel estimé</span><b>{meurFromM(first.resultat_meur)}</b></div>
              <div className="kpi"><span>Marge d'exploitation</span><b>{first.marge_pct.toFixed(1).replace(".", ",")} %</b></div>
              <div className="kpi hl"><span>Recommandation</span><b style={{ fontSize: 17, fontFamily: "var(--sans)" }}>{verdictShort(first.verdict)}</b></div>
            </div>
          </div>
        </section>
      )}

      {/* 8. Valeur */}
      <section className="section dark">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">Pourquoi c'est utile</p>
            <h2>Ce que CAP change pour une équipe réseau</h2>
          </div>
          <div className="grid g2">
            <div className="card"><h3>Gagner du temps sur la collecte</h3><p>La préparation qui prend des jours est faite en quelques secondes. L'analyste consacre son temps au jugement, pas à la saisie.</p></div>
            <div className="card"><h3>Comparer avec une seule méthode</h3><p>Toutes les destinations sont évaluées de la même façon, avec les mêmes hypothèses. Le classement est explicable critère par critère.</p></div>
            <div className="card"><h3>Faire confiance aux chiffres</h3><p>Chaque valeur renvoie à sa source et à sa formule. Les données manquantes ou masquées sont signalées, jamais comblées en silence.</p></div>
            <div className="card"><h3>Se brancher sur les données internes</h3><p>La démonstration utilise des données publiques. Dans une compagnie, on remplace la source par ses propres tables, sans toucher aux agents ni à l'interface.</p></div>
          </div>
          <p className="muted small" style={{ marginTop: 28 }}>
            Données publiques : la France est publiée par Eurostat jusqu'à {month(lastFr)}. Les limites du projet sont
            détaillées sur la page <Link href="/methode#limites">Comment ça marche</Link>.
          </p>
        </div>
      </section>

      {/* 9. Essayer */}
      <section className="section">
        <div className="wrap">
          <div className="section-head">
            <p className="eyebrow">À vous</p>
            <h2>Quatre façons de voir CAP en marche</h2>
          </div>
          <div className="grid g2">
            <Link href="/marche" className="card" style={{ textDecoration: "none" }}>
              <span className="num">Étudier · en direct</span><h3>L'étude de marché à la demande</h3>
              <p>Tapez n'importe quelle destination, desservie ou non : trafic de Paris face aux 16 hubs, évolution depuis 2019, simulation de la ligne.</p>
            </Link>
            <Link href="/agents" className="card accent" style={{ textDecoration: "none" }}>
              <span className="num">Agents IA · en direct</span><h3>Posez une question aux agents</h3>
              <p>Regardez l'Analyste choisir ses outils, interroger BigQuery, se faire contredire, puis répondre. Chaque décision et chaque chiffre sont affichés.</p>
            </Link>
            <Link href="/radar" className="card" style={{ textDecoration: "none" }}>
              <span className="num">Détecter</span><h3>Le radar des opportunités</h3>
              <p>Toutes les destinations long-courrier que Paris ne dessert pas, classées par un score transparent, chacune avec son dossier.</p>
            </Link>
            <Link href="/gcp" className="card" style={{ textDecoration: "none" }}>
              <span className="num">Sous le capot</span><h3>L'infrastructure Google Cloud</h3>
              <p>BigQuery table par table, le SQL exécuté, le rafraîchissement mensuel et un test de l'API en direct.</p>
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
