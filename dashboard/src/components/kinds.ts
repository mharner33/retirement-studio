export const KIND_LABELS: Record<string, string> = {
  pretax: "Pre-tax",
  roth: "Roth",
  taxable: "Taxable",
  cash: "Cash",
  hsa: "HSA",
};

export function sum(values: Record<string, number>): number {
  return Object.values(values).reduce((a, b) => a + b, 0);
}
