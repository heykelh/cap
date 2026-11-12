// Portage en TypeScript du modèle Python economics/model.py, pour recalculer dans le navigateur.
// Mêmes formules, mêmes conventions : une fréquence = un aller-retour par semaine (2 vols).

export type Inputs = {
  distanceKm: number;
  frequenciesPerWeek: number;
  seatsPerFlight: number;
  loadFactor: number;
  yieldEurPerRpk: number;
  costEurPerAsk: number;
  fuelEurPerAsk: number;
  weeksPerYear: number;
  fuelPriceChange: number;
  marketPaxPerYear: number | null;
};

export type Result = {
  flights: number;
  seats: number;
  ask: number;
  passengers: number;
  revenue: number;
  fuelCost: number;
  otherCost: number;
  totalCost: number;
  operatingResult: number;
  margin: number;
  breakevenLoadFactor: number;
  marketShare: number | null;
};

export function evaluate(x: Inputs): Result {
  const flights = 2 * x.frequenciesPerWeek * x.weeksPerYear;
  const seats = flights * x.seatsPerFlight;
  const ask = seats * x.distanceKm;
  const rpk = ask * x.loadFactor;
  const passengers = seats * x.loadFactor;
  const revenue = rpk * x.yieldEurPerRpk;
  const fuelCost = ask * x.fuelEurPerAsk * (1 + x.fuelPriceChange);
  const otherCost = ask * (x.costEurPerAsk - x.fuelEurPerAsk);
  const totalCost = fuelCost + otherCost;
  const operatingResult = revenue - totalCost;
  return {
    flights,
    seats,
    ask,
    passengers,
    revenue,
    fuelCost,
    otherCost,
    totalCost,
    operatingResult,
    margin: revenue > 0 ? operatingResult / revenue : 0,
    breakevenLoadFactor: totalCost / ask / x.yieldEurPerRpk,
    marketShare: x.marketPaxPerYear ? passengers / x.marketPaxPerYear : null,
  };
}

// Mêmes variations que le modèle Python (diagramme en tornade).
export function sensitivity(x: Inputs) {
  const run = (y: Inputs) => evaluate(y).operatingResult;
  const other = x.costEurPerAsk - x.fuelEurPerAsk;
  const rows = [
    {
      label: "Remplissage −5 pts / +5 pts",
      low: run({ ...x, loadFactor: Math.max(0.01, x.loadFactor - 0.05) }),
      high: run({ ...x, loadFactor: Math.min(1, x.loadFactor + 0.05) }),
    },
    {
      label: "Recette par passager −10 % / +10 %",
      low: run({ ...x, yieldEurPerRpk: x.yieldEurPerRpk * 0.9 }),
      high: run({ ...x, yieldEurPerRpk: x.yieldEurPerRpk * 1.1 }),
    },
    {
      label: "Coûts hors carburant −5 % / +5 %",
      low: run({ ...x, costEurPerAsk: other * 0.95 + x.fuelEurPerAsk }),
      high: run({ ...x, costEurPerAsk: other * 1.05 + x.fuelEurPerAsk }),
    },
    {
      label: "Prix du carburant −20 % / +20 %",
      low: run({ ...x, fuelPriceChange: x.fuelPriceChange - 0.2 }),
      high: run({ ...x, fuelPriceChange: x.fuelPriceChange + 0.2 }),
    },
  ];
  return rows
    .map((r) => ({ ...r, amplitude: Math.abs(r.high - r.low) }))
    .sort((a, b) => b.amplitude - a.amplitude);
}
