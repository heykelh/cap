// Contenu éditorial : chiffres du projet et chronologie de construction.
// Les chiffres viennent des sorties réelles du pipeline, aux dates indiquées.

export const PROJECT_FIGURES = [
  { value: "1 439 824", label: "lignes de trafic aérien chargées depuis Eurostat", note: "33 pays déclarants, depuis 2019" },
  { value: "481 660", label: "combinaisons route et mois après nettoyage", note: "passagers, sièges et vols réunis" },
  { value: "182", label: "destinations au radar d'opportunités", note: "après élimination des faux positifs" },
  { value: "≈ 3 s", label: "pour instruire un dossier complet", note: "six étapes, requêtes BigQuery et rédaction comprises" },
  { value: "1 / mois", label: "rafraîchissement automatique", note: "Cloud Scheduler et Cloud Run, sans intervention" },
  { value: "0", label: "chiffre écrit par l'intelligence artificielle", note: "tous les montants sortent du code" },
];

export type Milestone = {
  date: string;
  phase: string;
  title: string;
  text: string;
  lesson?: string;
};

export const TIMELINE: Milestone[] = [
  {
    date: "21 octobre 2026",
    phase: "Cadrage",
    title: "Partir du métier, pas de la technologie",
    text: "Étude du travail d'une équipe de planification réseau : repérer des routes à ouvrir, construire et défendre un business plan, suivre la santé des lignes existantes. CAP est conçu pour accélérer ces trois gestes, avec des données publiques vérifiables.",
  },
  {
    date: "26 octobre 2026",
    phase: "Socle",
    title: "Un entrepôt de données sur Google Cloud",
    text: "Création du projet GCP et de l'entrepôt BigQuery, organisé en trois couches : bronze pour les données brutes, silver pour les données nettoyées, gold pour les indicateurs. Authentification séparée pour les scripts Python et pour les outils en ligne de commande.",
  },
  {
    date: "26 octobre 2026",
    phase: "Bronze",
    title: "Charger 1,4 million de lignes de trafic aérien",
    text: "Premier essai sur la France seule, puis chargement complet : 33 pays, trois mesures par route et par mois (passagers, sièges offerts, vols). Eurostat met parfois les grosses demandes en file d'attente : le script a été réécrit pour attendre et récupérer les données automatiquement.",
    lesson: "Ne jamais supposer qu'une source répond toujours de la même façon.",
  },
  {
    date: "26 octobre 2026",
    phase: "Silver",
    title: "Nettoyer, unifier et mesurer la qualité",
    text: "Une ligne par route et par mois, enrichie des villes, des codes aéroport et de la distance. Chaque pays publie à son rythme : la France s'arrête à décembre 2024. Les analyses utilisent donc les douze derniers mois publiés de chaque pays, jamais une année fixe.",
    lesson: "La fraîcheur des données se mesure et s'affiche, elle ne se suppose pas.",
  },
  {
    date: "26 octobre 2026",
    phase: "Gold",
    title: "Premier radar, premières anomalies",
    text: "Le radar classe 206 destinations, mais Dubaï et Atlanta y figurent comme « non desservies depuis Paris », ce qui est faux. Eurostat masque les volumes de certaines routes pour raison de confidentialité (Atlanta l'est 72 mois sur 72). Ces lignes sont désormais conservées et signalées au lieu d'être jetées.",
    lesson: "Une donnée absente n'est pas une donnée nulle.",
  },
  {
    date: "27 octobre 2026",
    phase: "Gouvernance",
    title: "La règle de la même ville et le jugement de l'analyste",
    text: "Doha apparaissait sous l'ancien code de son aéroport. Nouvelle règle : si Paris dessert déjà la ville, ce n'est pas une opportunité. Ajout d'un fichier de corrections tenu par l'analyste, où chaque ligne exige une source et une date. Le radar passe à 182 destinations crédibles.",
  },
  {
    date: "28 octobre 2026",
    phase: "Modèle",
    title: "Un compte de résultat transparent",
    text: "Le modèle économique calcule recette, coûts, marge et remplissage d'équilibre. Chaque hypothèse vient du communiqué annuel public d'Air France-KLM, page citée, et le modèle refuse de démarrer si une hypothèse n'a pas de source. Le site recalcule avec les mêmes formules, au centime près.",
  },
  {
    date: "28 octobre 2026",
    phase: "Instruction",
    title: "Une chaîne d'instruction en six étapes et un garde-fou",
    text: "Construction de la chaîne d'instruction avec LangGraph : éclaireur, marché, concurrence, économiste, avocat du diable, rédacteur. Un workflow volontairement déterministe, car un business plan doit être reproductible. Règle fondatrice : l'intelligence artificielle rédige, le code calcule. Un contrôle automatique rejette tout texte qui contient un chiffre écrit à la main. Testé avec une IA volontairement menteuse : ses chiffres inventés n'atteignent jamais la note.",
    lesson: "Un outil d'aide à la décision doit rester juste même quand l'IA se trompe.",
  },
  {
    date: "Début novembre 2026",
    phase: "Fiabilité",
    title: "Résister aux pannes des fournisseurs d'IA",
    text: "Saturations passagères, modèle retiré par son éditeur, quotas atteints au milieu d'un lot : ajout d'un délai maximal, d'un disjoncteur par dossier, d'une chaîne de relais entre fournisseurs et d'une reprise automatique. Résultat : tous les dossiers rédigés par l'IA, en trois secondes environ chacun.",
  },
  {
    date: "9 novembre 2026",
    phase: "Couverture",
    title: "Un dossier pour chaque destination long-courrier",
    text: "Plutôt qu'un échantillon arbitraire, une règle simple et défendable : chaque destination long-courrier du radar reçoit son dossier complet. Le moyen-courrier reste au radar mais sans dossier, car le modèle économique est calibré sur le long-courrier.",
  },
  {
    date: "Novembre 2026",
    phase: "Production",
    title: "Du prototype au service : Cloud Run, direct et rafraîchissement mensuel",
    text: "La chaîne d'instruction et l'étude de marché deviennent une API sur Cloud Run, interrogeable en direct depuis ce site pour n'importe quelle destination. Un job mensuel, déclenché par Cloud Scheduler, recharge les sources, recalcule BigQuery, refait instruire les dossiers et republie le site. Chaque requête est tracée : texte SQL, octets lus, durée.",
    lesson: "Une démonstration convaincante montre la machine en marche, pas seulement le résultat.",
  },
  {
    date: "Novembre 2026",
    phase: "Agents IA",
    title: "De vrais agents : l'Analyste et le Contradicteur",
    text: "La chaîne d'instruction suit un ordre fixe : c'est un workflow, pas un agent. Pour les questions ouvertes, CAP se dote de deux agents IA qui décident eux-mêmes de leurs actions. L'Analyste choisit quels outils appeler (radar, étude de marché, simulation, sensibilités), examine les résultats et approfondit quand un chiffre l'interpelle. Le Contradicteur vérifie à son tour avec les mêmes outils et renvoie ses objections. Le garde-fou reste en place : chaque chiffre cité provient d'un outil.",
    lesson: "Workflow quand le résultat doit être reproductible, agent quand le chemin dépend de ce qu'on découvre.",
  },
];

export const TECHNOLOGIES = [
  { group: "Sources", name: "Eurostat (API SDMX)", role: "Trafic aérien officiel européen : passagers, sièges et vols par paire d'aéroports et par mois." },
  { group: "Sources", name: "OurAirports", role: "Référentiel mondial des aéroports : codes, villes, coordonnées GPS." },
  { group: "Sources", name: "Communiqué annuel Air France-KLM 2025", role: "Hypothèses économiques publiques : recette et coût par kilomètre, remplissage par région." },
  { group: "Données", name: "Python, pandas, pyarrow", role: "Téléchargement, contrôle et mise en forme des données avant chargement." },
  { group: "Données", name: "Google BigQuery", role: "Entrepôt de données dans le cloud, organisé en trois couches : brute, nettoyée, prête à l'analyse." },
  { group: "Données", name: "SQL", role: "Toutes les transformations : fenêtres de douze mois, règles de qualité, score d'opportunité." },
  { group: "Intelligence", name: "FastAPI et Server-Sent Events", role: "L'API qui diffuse en direct la chaîne d'instruction et le raisonnement des agents IA." },
  { group: "Intelligence", name: "Agents à appel d'outils", role: "L'Analyste et le Contradicteur : un modèle de langage (Groq, Gemini en relais) qui choisit ses outils en boucle, encadré par le garde-fou." },
  { group: "Intelligence", name: "LangGraph", role: "Orchestration de la chaîne d'instruction : ordre de passage, contrôle, réécriture, plan de secours." },
  { group: "Intelligence", name: "Groq (gpt-oss-120b) et Gemini", role: "Rédaction de la note de synthèse, avec bascule automatique d'un fournisseur à l'autre." },
  { group: "Qualité", name: "pytest", role: "36 tests automatiques : formules, cohérence des résultats, résistance aux pannes et aux erreurs de l'IA." },
  { group: "Production", name: "Cloud Run (service et job)", role: "L'API en direct (étude de marché, chaîne d'instruction, agents IA) et le rafraîchissement mensuel, à partir d'une même image Docker." },
  { group: "Production", name: "Cloud Scheduler, Cloud Storage, Secret Manager", role: "Déclenchement mensuel, publication des données du site, clés d'IA hors du code." },
  { group: "Site", name: "Next.js, React, TypeScript", role: "Ce site : pages générées à chaque rafraîchissement, appels en direct à l'API, recalcul instantané des scénarios." },
  { group: "Site", name: "Vercel et GitHub", role: "Hébergement du site et versionnement de tout le code." },
];
