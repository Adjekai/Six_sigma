export async function getScenarios() {
  const response = await fetch("/api/scenarios");
  if (!response.ok) throw new Error("Could not load scenarios");
  return response.json();
}

export async function getDashboard({ scenario, refrigeratorId, horizonDays }) {
  const parameters = new URLSearchParams({
    scenario,
    horizon_operating_days: String(horizonDays),
    temperature_window_hours: "24",
  });
  if (refrigeratorId) parameters.set("refrigerator_id", refrigeratorId);
  const response = await fetch(`/api/dashboard?${parameters}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Could not load dashboard data");
  }
  return response.json();
}
