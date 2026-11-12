import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";

export const metadata: Metadata = {
  title: "CAP · Instruire une ouverture de ligne aérienne",
  description:
    "CAP détecte les destinations qui manquent au réseau de Paris CDG et instruit un dossier d'ouverture complet : marché, concurrence, rentabilité, risques. Projet de Heykel Hachiche.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Kanit:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,500&display=swap"
        />
      </head>
      <body>
        <a href="#contenu" className="sr-skip">
          Aller au contenu
        </a>
        <Nav />
        <main id="contenu">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
