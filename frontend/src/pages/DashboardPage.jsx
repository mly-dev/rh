import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { get } from "../api";

const S1 = "#2a78d6";
const S2 = "#eb6834";
const S3 = "#1baf7a";

function StatTile({ label, value, unit }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-semibold">
        {value}
        {unit ? <span className="text-sm font-normal text-gray-500"> {unit}</span> : null}
      </p>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-medium mb-2 text-sm">{title}</h3>
      {children}
    </div>
  );
}

function toBarData(byRegion) {
  return Object.entries(byRegion || {})
    .map(([region, value]) => ({ region, value }))
    .sort((a, b) => b.value - a.value);
}

export default function DashboardPage() {
  const [zone, setZone] = useState("");
  const [zones, setZones] = useState([]);
  const [summary, setSummary] = useState(null);
  const [indicatorName, setIndicatorName] = useState("");
  const [indicator, setIndicator] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    get("/zones").then(setZones).catch(() => {});
  }, []);

  useEffect(() => {
    setError("");
    get("/dashboard/summary", { zone })
      .then(setSummary)
      .catch((e) => setError(e.message));
  }, [zone]);

  useEffect(() => {
    if (!indicatorName) return setIndicator(null);
    get("/dashboard/indicator", { name: indicatorName, zone })
      .then(setIndicator)
      .catch(() => setIndicator(null));
  }, [indicatorName, zone]);

  const sitesParRegion = useMemo(
    () => toBarData(summary?.sites?.by_region),
    [summary]
  );
  const incidentsParRegion = useMemo(
    () => toBarData(summary?.incidents?.by_region),
    [summary]
  );
  const sitesParType = useMemo(
    () => toBarData(summary?.sites?.by_type).map(({ region, value }) => ({ type: region, value })),
    [summary]
  );

  if (error) return <p className="text-red-600">Erreur : {error}</p>;
  if (!summary) return <p className="text-gray-500">Chargement…</p>;

  const stocksSeries = (summary.stocks?.series || []).filter((s) => s.period !== "sans période");
  const hasData =
    summary.sites.total > 0 ||
    summary.incidents.total > 0 ||
    summary.stocks.records > 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-gray-600">Zone :</label>
        <select
          value={zone}
          onChange={(e) => setZone(e.target.value)}
          className="border border-gray-300 rounded-md px-2 py-1.5 text-sm bg-white"
        >
          <option value="">Niger (tout le pays)</option>
          {zones.map((r) => (
            <option key={r.id} value={r.name}>
              {r.name}
            </option>
          ))}
        </select>
        <label className="text-sm text-gray-600 ml-4">Indicateur :</label>
        <select
          value={indicatorName}
          onChange={(e) => setIndicatorName(e.target.value)}
          className="border border-gray-300 rounded-md px-2 py-1.5 text-sm bg-white"
        >
          <option value="">—</option>
          {(summary.catalog?.indicators || []).map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Sites" value={summary.sites.total} />
        <StatTile label="Incidents (agrégés)" value={summary.incidents.total} />
        <StatTile label="Relevés de stocks" value={summary.stocks.records} />
        <StatTile
          label="Indicateurs suivis"
          value={(summary.catalog?.indicators || []).length}
        />
      </div>

      {!hasData && (
        <p className="text-gray-500 bg-white border border-gray-200 rounded-lg p-6 text-center">
          Aucune donnée pour cette zone. Importez un fichier depuis l'onglet
          « Import » ou chargez les jeux de démonstration (voir README).
        </p>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        {sitesParRegion.length > 0 && (
          <Card title="Sites par région">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={sitesParRegion} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="region" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" name="Sites" fill={S1} radius={[4, 4, 0, 0]} maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        )}
        {incidentsParRegion.length > 0 && (
          <Card title="Incidents par région (fréquence agrégée)">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={incidentsParRegion} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="region" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" name="Incidents" fill={S2} radius={[4, 4, 0, 0]} maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        )}
        {sitesParType.length > 0 && (
          <Card title="Répartition des sites par type">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={sitesParType} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                <YAxis type="category" dataKey="type" tick={{ fontSize: 11 }} width={120} />
                <Tooltip />
                <Bar dataKey="value" name="Sites" fill={S1} radius={[0, 4, 4, 0]} maxBarSize={22} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        )}
        {stocksSeries.length > 1 && (
          <Card title="Évolution des stocks (toutes ressources)">
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={stocksSeries} margin={{ left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="quantity"
                  name="Quantité"
                  stroke={S3}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        )}
        {indicator && indicator.series?.length > 0 && (
          <Card
            title={`Indicateur « ${indicator.indicator} » — ${indicator.zone}${
              indicator.unit ? ` (${indicator.unit})` : ""
            }`}
          >
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={indicator.series} margin={{ left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="value"
                  name={indicator.indicator}
                  stroke={S1}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
            <p className="text-sm text-gray-500 mt-1">
              Total : {indicator.total} {indicator.unit || ""}
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
