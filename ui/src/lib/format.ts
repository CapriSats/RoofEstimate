export const formatCurrency = (n: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);

export const formatSqft = (n: number) =>
  new Intl.NumberFormat("en-US").format(Math.round(n));

export const formatLatLon = (lat: number, lon: number) =>
  `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
