/* Pure resource-chart normalization helpers. Keep API data handling testable without a browser. */
function finiteNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function percentMetric(value) {
  const number = finiteNumber(value);
  if (number === null) return null;
  return Math.min(100, Math.max(0, number));
}

export function makeResourceSample(resources = {}, hardware = {}) {
  const cpu = percentMetric(resources?.cpu_percent);
  const ram = percentMetric(resources?.ram_percent);
  const totalVram = finiteNumber(hardware?.gpu_vram_gb);
  const freeVram = finiteNumber(resources?.gpu_free_vram_gb);

  let vram = null;
  if (totalVram !== null && totalVram > 0 && freeVram !== null) {
    const boundedFree = Math.min(totalVram, Math.max(0, freeVram));
    vram = percentMetric(((totalVram - boundedFree) / totalVram) * 100);
  }

  return {
    cpu_percent: cpu,
    ram_percent: ram,
    vram_percent: vram,
    gpu_free_vram_gb: freeVram === null ? null : Math.max(0, freeVram),
    gpu_total_vram_gb: totalVram !== null && totalVram > 0 ? totalVram : null,
  };
}

export function resourceSeries(history) {
  const rows = Array.isArray(history) ? history : [];
  const cpu = rows.map((row) => percentMetric(row?.cpu_percent));
  const ram = rows.map((row) => percentMetric(row?.ram_percent));
  const vram = rows.map((row) => percentMetric(row?.vram_percent));
  return {cpu, ram, vram, hasVram: vram.some((value) => value !== null)};
}

function roundedPercent(value) {
  const number = percentMetric(value);
  return number === null ? '--' : `${Math.round(number)}%`;
}

export function resourceSampleLabel(sample = {}) {
  const parts = [
    `CPU ${roundedPercent(sample?.cpu_percent)}`,
    `RAM ${roundedPercent(sample?.ram_percent)}`,
  ];
  const vram = percentMetric(sample?.vram_percent);
  if (vram !== null) parts.push(`VRAM ${Math.round(vram)}%`);
  return parts.join(' · ');
}
