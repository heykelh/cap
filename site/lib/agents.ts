// Fiche de chaque agent : ce qu'il reçoit, ce qu'il fait, ce qu'il rend.
export const AGENTS = [
  {
    name: "Éclaireur",
    role: "Explique pourquoi la destination ressort du radar.",
    recoit: "Le code IATA de la destination.",
    fait: "Lit la ligne du radar dans BigQuery (cap_gold.opportunities) : score, segment, distance, rang sur chaque critère.",
    rend: "La fiche d'identité de l'opportunité et son classement critère par critère.",
  },
  {
    name: "Marché",
    role: "Mesure la demande déjà servie par les hubs concurrents.",
    recoit: "La destination et la liste des 16 hubs européens observés.",
    fait: "Interroge cap_gold.route_window : passagers, évolution et remplissage de chaque hub vers la destination sur 12 mois.",
    rend: "Taille du marché, croissance, concentration sur un hub, date des dernières données.",
  },
  {
    name: "Concurrence",
    role: "Décrit comment les Parisiens s'y rendent aujourd'hui.",
    recoit: "Les hubs qui desservent la destination.",
    fait: "Interroge le trafic CDG vers chacun de ces hubs : c'est le réservoir de clients en correspondance chez les concurrents.",
    rend: "Les liaisons Paris-hubs, leurs volumes, les données masquées.",
  },
  {
    name: "Économiste",
    role: "Calcule le compte de résultat de la ligne.",
    recoit: "Le scénario (fréquence, appareil, région) et le marché mesuré.",
    fait: "Applique le modèle CAP (aucune IA) avec les hypothèses sourcées du communiqué Air France-KLM 2025, puis teste les sensibilités.",
    rend: "Recette, coûts, résultat, marge, remplissage d'équilibre, part de marché à capter.",
  },
  {
    name: "Avocat du diable",
    role: "Cherche les failles du dossier.",
    recoit: "Tous les faits produits par les agents précédents.",
    fait: "Applique des règles explicites : part de marché irréaliste, marge fragile, demande en baisse, hub unique, données anciennes, marché surveillé.",
    rend: "Les objections classées par gravité et la recommandation qui en découle.",
  },
  {
    name: "Rédacteur",
    role: "Écrit la note d'une page, sous contrôle.",
    recoit: "Les analyses des agents, avec des balises à la place des chiffres.",
    fait: "L'IA rédige avec des balises comme {{resultat_meur}}. Le garde-fou rejette tout chiffre écrit à la main, puis le code insère les valeurs calculées.",
    rend: "La note finale, dont chaque chiffre vient du calcul.",
  },
] as const;

export type AgentName = (typeof AGENTS)[number]["name"];
