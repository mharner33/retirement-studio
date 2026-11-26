const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function formatUsd(n: number): string {
  return usd.format(n === 0 ? 0 : n);
}

export function formatPercent(rate: number): string {
  return `${(Math.floor(rate * 1000 + 1e-9) / 10).toFixed(1)}%`;
}

export function formatCompact(n: number): string {
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  const thousands = Math.round(abs / 1000);
  if (thousands === 0) {
    return "$0";
  }
  return thousands >= 1000
    ? `${sign}$${(abs / 1_000_000).toFixed(1)}M`
    : `${sign}$${String(thousands)}K`;
}
