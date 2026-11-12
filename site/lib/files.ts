// Noms de fichiers interdits par Windows (PRN = Pristina, CON, AUX, NUL…) : même règle que agents/market.py.
const WINDOWS_RESERVED = new Set(["CON", "PRN", "AUX", "NUL"]);

export const fileKey = (iata: string) => {
  const code = iata.toUpperCase();
  return WINDOWS_RESERVED.has(code) ? `${code}_` : code;
};
