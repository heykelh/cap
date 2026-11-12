// Logo original de CAP : une boussole stylisée (le « cap » à tenir).
export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 34 34" aria-hidden="true">
      <circle cx="17" cy="17" r="15" fill="none" stroke="#f08f8f" strokeWidth="1.6" />
      <path d="M17 5 L21 17 L17 29 L13 17 Z" fill="none" stroke="#ffffff" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M17 5 L21 17 L13 17 Z" fill="#ffffff" />
      <circle cx="17" cy="17" r="2.2" fill="#c42d35" />
    </svg>
  );
}
