const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function formatUsd(n: number): string {
  return usd.format(n === 0 ? 0 : n);
}
