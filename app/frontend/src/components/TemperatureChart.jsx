export default function TemperatureChart({ series, lower = 1, upper = 6 }) {
  const valid = series.filter((row) => row.reading_valid && row.temperature_c !== null);
  if (!valid.length) return <p className="empty">No valid readings in this window.</p>;

  const width = 820;
  const height = 260;
  const inset = 34;
  const yMin = 0;
  const yMax = 8;
  const x = (index) => inset + (index / Math.max(valid.length - 1, 1)) * (width - inset * 2);
  const y = (value) => height - inset - ((value - yMin) / (yMax - yMin)) * (height - inset * 2);
  const points = valid.map((row, index) => `${x(index)},${y(row.temperature_c)}`).join(" ");

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Refrigerator temperature with configured storage limits">
        <rect x={inset} y={y(upper)} width={width - 2 * inset} height={y(lower) - y(upper)} className="limit-band" />
        {[0, 2, 4, 6, 8].map((tick) => (
          <g key={tick}>
            <line x1={inset} x2={width - inset} y1={y(tick)} y2={y(tick)} className="grid" />
            <text x="2" y={y(tick) + 4}>{tick} °C</text>
          </g>
        ))}
        <polyline points={points} className="temperature-line" />
        {valid.map((row, index) => {
          const breached = row.temperature_c < lower || row.temperature_c > upper;
          return <circle key={row.timestamp_utc} cx={x(index)} cy={y(row.temperature_c)} r="3.5" className={breached ? "point breach" : "point"} />;
        })}
      </svg>
      <p className="chart-note">Shaded area: configured 1–6 °C demonstration range. Equality is in range.</p>
    </div>
  );
}
