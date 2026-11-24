const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function formatUsd(n: number): string {
  return usd.format(n === 0 ? 0 : n);
}

export function formatPercent(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}
