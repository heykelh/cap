// Médias facultatifs. Le site fonctionne sans : la carte animée tient lieu de visuel principal.
// Pour ajouter une vidéo ou des photos libres de droits (Pexels, Unsplash), dépose les fichiers
// dans public/media/ puis renseigne leur nom ici. Laisser une chaîne vide pour ne rien afficher.
export const MEDIA = {
  // Courte boucle vidéo muette, ex. « hero.mp4 » (format MP4 H.264, moins de 8 Mo conseillé).
  heroVideo: "",
  // Image affichée avant le chargement de la vidéo, ex. « hero.jpg ».
  heroPoster: "",
  // Bandeau photo de la page d'accueil, ex. « hub.jpg ».
  bandPhoto: "",
  // Crédit à afficher sous les médias, ex. « Photos : Pexels ».
  credit: "",
};

export const media = (file: string) => (file ? `/media/${file}` : "");
