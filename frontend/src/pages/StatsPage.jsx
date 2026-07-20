// Задачи 24/63: страница «Статистика». Все цифры считает бэкенд (/stats) —
// фронт только рисует. Так одна и та же метрика не разъедется между экраном
// и промптом AI-инсайтов.
//
// Страница грузится отдельным чанком (React.lazy в App): recharts весит
// заметно больше остального приложения, а заходят сюда редко.
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import * as api from "../api";
import { keys } from "../queryKeys";
import "../styles/stats.css";

const MONTH_NAMES = [
  "янв", "фев", "мар", "апр", "май", "июн",
  "июл", "авг", "сен", "окт", "ноя", "дек",
];

/** "2026-07" → "июл" (в январе добавляем год: иначе непонятно, где граница) */
function monthLabel(key) {
  const [year, month] = key.split("-");
  const name = MONTH_NAMES[Number(month) - 1] ?? key;
  return month === "01" ? `${name} ${year.slice(2)}` : name;
}

function StatCard({ label, value, hint }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint ? <div className="stat-hint">{hint}</div> : null}
    </div>
  );
}

/** Топ авторов/жанров: полоска рисуется долей от максимума — без библиотеки,
 *  потому что длинные имена в горизонтальном графике recharts обрезаются. */
function TopList({ title, items, nameKey, empty }) {
  if (!items.length) return (
    <section className="stat-block">
      <h2 className="stat-title">{title}</h2>
      <p className="muted">{empty}</p>
    </section>
  );
  const max = Math.max(...items.map((i) => i.count));
  return (
    <section className="stat-block">
      <h2 className="stat-title">{title}</h2>
      <ul className="top-list">
        {items.map((item) => (
          <li key={item[nameKey]} className="top-row">
            <span className="top-name">{item[nameKey]}</span>
            <span className="top-bar-track">
              <span
                className="top-bar"
                style={{ width: `${(item.count / max) * 100}%` }}
              />
            </span>
            <span className="top-count">{item.count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Chart({ data, dataKey, xKey, tickFormatter, labelFormatter, highlight }) {
  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -24, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey={xKey}
            tickFormatter={tickFormatter}
            tick={{ fill: "var(--muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "var(--muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "var(--surface)" }}
            labelFormatter={labelFormatter}
            formatter={(value) => [value, "книг"]}
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              color: "var(--text)",
            }}
          />
          <Bar dataKey={dataKey} radius={[4, 4, 0, 0]}>
            {data.map((row, i) => (
              <Cell
                key={i}
                // нулевые столбцы гасим: пустой месяц не должен выглядеть данными
                fill={row[dataKey] ? "var(--accent)" : "var(--border)"}
                opacity={highlight && i === data.length - 1 ? 1 : 0.85}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function StatsPage() {
  const stats = useQuery({ queryKey: keys.stats, queryFn: api.getStats });
  const insights = useMutation({ mutationFn: api.generateInsights });

  const data = stats.data;
  const nothingRead = data && data.totals.read === 0;

  return (
    <div className="stats-page">
      <header className="stats-header">
        <Link to="/" className="btn-ghost">
          ← В библиотеку
        </Link>
        <h1 className="title">Статистика</h1>
      </header>

      {stats.isPending ? <p className="muted">Считаю…</p> : null}
      {stats.isError ? (
        <p className="error">Не удалось загрузить статистику</p>
      ) : null}

      {data ? (
        <>
          <div className="stat-cards">
            <StatCard label="Прочитано" value={data.totals.read} />
            <StatCard label="Читаю" value={data.totals.reading} />
            <StatCard label="Хочу прочитать" value={data.totals.want} />
            <StatCard
              label="Страниц"
              value={data.pages_read.toLocaleString("ru-RU")}
              hint="только по книгам с известным объёмом"
            />
            <StatCard
              label="Средняя оценка"
              value={data.average_rating ?? "—"}
              hint={
                data.rated_count
                  ? `оценено книг: ${data.rated_count}`
                  : "оценок пока нет"
              }
            />
            <StatCard
              label="Месяцев подряд"
              value={data.streak_months}
              hint="читали хотя бы по книге"
            />
          </div>

          <section className="stat-block">
            <h2 className="stat-title">
              Прочитано по месяцам
              <span className="stat-note">
                в {data.this_year.year} году — {data.this_year.count}
              </span>
            </h2>
            {nothingRead ? (
              <p className="muted">
                Пока ни одной прочитанной книги. Отметьте книгу прочитанной —
                и здесь появится история.
              </p>
            ) : (
              <Chart
                data={data.by_month}
                dataKey="count"
                xKey="month"
                tickFormatter={monthLabel}
                labelFormatter={monthLabel}
                highlight
              />
            )}
          </section>

          {data.rated_count ? (
            <section className="stat-block">
              <h2 className="stat-title">Как вы оцениваете</h2>
              <Chart
                data={data.ratings}
                dataKey="count"
                xKey="rating"
                labelFormatter={(v) => `Оценка ${v}/10`}
              />
            </section>
          ) : null}

          <div className="stat-columns">
            <TopList
              title="Любимые авторы"
              items={data.top_authors}
              nameKey="author"
              empty="Появятся, когда будут прочитанные книги."
            />
            <TopList
              title="Частые жанры"
              items={data.top_genres}
              nameKey="genre"
              empty="Жанры подтягиваются из данных о книге."
            />
          </div>

          <section className="stat-block insights">
            <h2 className="stat-title">Наблюдения</h2>
            <p className="muted">
              AI посмотрит на цифры выше и найдёт закономерности. Считает всё
              бэкенд — модель только читает готовую сводку.
            </p>
            <button
              className="btn-ghost"
              onClick={() => insights.mutate()}
              disabled={insights.isPending || nothingRead}
            >
              {insights.isPending ? "Думаю…" : "Найти закономерности"}
            </button>

            {insights.isError ? (
              <p className="error">Не получилось. Попробуйте ещё раз.</p>
            ) : null}
            {insights.data?.detail === "no_data" ? (
              <p className="muted">Пока нечего толковать — нет прочитанных книг.</p>
            ) : null}
            {insights.data?.observations?.length ? (
              <ul className="insight-list">
                {insights.data.observations.map((text, i) => (
                  <li key={i}>{text}</li>
                ))}
              </ul>
            ) : null}
          </section>
        </>
      ) : null}
    </div>
  );
}

export default StatsPage;
