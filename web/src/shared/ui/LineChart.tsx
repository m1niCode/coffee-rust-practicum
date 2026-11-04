export interface Series {
  data: number[];
  /** имя CSS-переменной цвета, например '--s1' */
  color: string;
}

interface Props {
  series: Series[];
  xmax: number;
  ymin: number;
  ymax: number;
  percent?: boolean;
  label: string;
}

const W = 520, H = 240, L = 40, R = 14, T = 12, B = 28;

/** Простой SVG-график: цвета берутся из темы, подписи осей — общие для всех серий. */
export function LineChart({ series, xmax, ymin, ymax, percent, label }: Props) {
  const xs = (i: number) => L + (W - L - R) * (xmax <= 1 ? 0 : i / (xmax - 1));
  const ys = (v: number) => T + (H - T - B) * (1 - (v - ymin) / (ymax - ymin));
  const step = xmax > 40 ? 10 : xmax > 20 ? 5 : xmax > 10 ? 2 : 1;
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      {[0, 1, 2, 3, 4].map((k) => {
        const v = ymin + ((ymax - ymin) * k) / 4;
        return (
          <g key={k}>
            <line className="gl" x1={L} x2={W - R} y1={ys(v)} y2={ys(v)} />
            <text x={L - 6} y={ys(v) + 4} textAnchor="end">{percent ? Math.round(v * 100) + '%' : v.toFixed(2)}</text>
          </g>
        );
      })}
      {Array.from({ length: Math.ceil(xmax / step) }, (_, k) => k * step).map((i) => (
        <text key={i} x={xs(i)} y={H - 8} textAnchor="middle">{i + 1}</text>
      ))}
      {series.map((s, idx) => {
        if (!s.data.length) return null;
        const d = s.data.map((v, i) => `${i ? 'L' : 'M'}${xs(i).toFixed(1)} ${ys(v).toFixed(1)}`).join(' ');
        const last = s.data.length - 1;
        return (
          <g key={idx}>
            <path d={d} fill="none" stroke={`var(${s.color})`} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" />
            <circle cx={xs(last)} cy={ys(s.data[last] ?? 0)} r={4.5} fill={`var(${s.color})`} stroke="var(--surface)" strokeWidth={2} />
          </g>
        );
      })}
    </svg>
  );
}
