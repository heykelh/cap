"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Logo } from "./Logo";

const LINKS = [
  { href: "/", label: "Le projet" },
  { href: "/marche", label: "Étude de marché" },
  { href: "/radar", label: "Radar" },
  { href: "/agents", label: "Agents IA" },
  { href: "/gcp", label: "Sous le capot" },
  { href: "/methode", label: "Méthode" },
  { href: "/chronologie", label: "Chronologie" },
];

export function Nav() {
  const path = usePathname();
  return (
    <header className="nav">
      <nav className="wrap" aria-label="Navigation principale">
        <Link href="/" className="brand" aria-label="CAP, accueil">
          <Logo size={30} />
          <b>CAP</b>
          <span>Network Planning Copilot</span>
        </Link>
        <ul>
          {LINKS.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <li key={l.href}>
                <Link href={l.href} aria-current={active ? "page" : undefined}>
                  {l.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </header>
  );
}
