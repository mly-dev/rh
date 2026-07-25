import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { get } from "../api";

// Rampe séquentielle (un seul ton, clair → foncé) pour la choroplèthe
const RAMP = ["#eff6ff", "#bfdbfe", "#7db3ec", "#2a78d6", "#1d4ed8"];
const STATUS_COLORS = {
  fonctionnel: "#008300",
  partiel: "#c98500",
  non_fonctionnel: "#d92d20",
  inconnu: "#6b7280",
};

const METRICS = [
  { value: "sites", label: "Nombre de sites" },
  { value: "incidents", label: "Incidents (fréquence agrégée)" },
  { value: "stocks", label: "Stocks (quantités)" },
  { value: "indicator", label: "Indicateur (somme)" },
];

function rampColor(value, max) {
  if (!value || max <= 0) return RAMP[0];
  const idx = Math.min(RAMP.length - 1, Math.ceil((value / max) * (RAMP.length - 1)));
  return RAMP[idx];
}

export default function MapPage() {
  const mapRef = useRef(null);
  const layersRef = useRef({ geo: null, markers: null });
  const [metric, setMetric] = useState("sites");
  const [catalog, setCatalog] = useState(null);
  const [filters, setFilters] = useState({});
  const [showSites, setShowSites] = useState(true);
  const [legendMax, setLegendMax] = useState(0);

  useEffect(() => {
    get("/catalog").then(setCatalog).catch(() => {});
  }, []);

  useEffect(() => {
    const map = L.map("map", { center: [17.2, 9.0], zoom: 5.4, zoomSnap: 0.2 });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
      opacity: 0.55,
    }).addTo(map);
    mapRef.current = map;
    return () => map.remove();
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let cancelled = false;

    async function refresh() {
      const params = { metric, ...filters };
      const [geo, stats] = await Promise.all([
        get("/zones/geojson", { level: "region" }),
        get("/dashboard/map", params),
      ]);
      if (cancelled) return;
      const values = stats.by_region || {};
      const max = Math.max(0, ...Object.values(values));
      setLegendMax(max);

      if (layersRef.current.geo) map.removeLayer(layersRef.current.geo);
      layersRef.current.geo = L.geoJSON(geo, {
        style: (f) => ({
          fillColor: rampColor(values[f.properties.name], max),
          fillOpacity: 0.75,
          color: "#ffffff",
          weight: 2,
        }),
        onEachFeature: (f, layer) => {
          const v = values[f.properties.name] ?? 0;
          layer.bindTooltip(
            `<strong>${f.properties.name}</strong><br/>${
              METRICS.find((m) => m.value === metric)?.label
            } : ${v}`,
            { sticky: true }
          );
        },
      }).addTo(map);

      if (layersRef.current.markers) map.removeLayer(layersRef.current.markers);
      if (showSites) {
        const sites = await get("/sites", {
          site_type: filters.site_type,
          status: filters.status,
        });
        if (cancelled) return;
        const group = L.layerGroup(
          sites
            .filter((s) => s.lat != null && s.lon != null)
            .map((s) =>
              L.circleMarker([s.lat, s.lon], {
                radius: 6,
                color: "#ffffff",
                weight: 1.5,
                fillColor: STATUS_COLORS[s.status] || STATUS_COLORS.inconnu,
                fillOpacity: 0.95,
              }).bindTooltip(
                `<strong>${s.name}</strong><br/>${s.site_type} · ${s.zone}<br/>État : ${s.status}` +
                  (s.capacity ? `<br/>Capacité : ${s.capacity} ${s.capacity_unit || ""}` : "")
              )
            )
        );
        layersRef.current.markers = group.addTo(map);
      }
    }

    refresh().catch(console.error);
    return () => {
      cancelled = true;
    };
  }, [metric, filters, showSites]);

  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value || undefined }));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 bg-white border border-gray-200 rounded-lg p-3">
        <label className="text-sm text-gray-600">Métrique :</label>
        <select value={metric} onChange={(e) => setMetric(e.target.value)}
                className="border border-gray-300 rounded-md px-2 py-1.5 text-sm bg-white">
          {METRICS.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
        {metric === "sites" && (
          <>
            <select onChange={set("site_type")} className="border border-gray-300 rounded-md px-2 py-1.5 text-sm bg-white">
              <option value="">Tous les types</option>
              {(catalog?.site_types || []).map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <select onChange={set("status")} className="border border-gray-300 rounded-md px-2 py-1.5 text-sm bg-white">
              <option value="">Tous les états</option>
              {(catalog?.site_statuses || []).map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </>
        )}
        {metric === "incidents" && (
          <select onChange={set("incident_type")} className="border border-gray-300 rounded-md px-2 py-1.5 text-sm bg-white">
            <option value="">Tous les types</option>
            {(catalog?.incident_types || []).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        )}
        {metric === "indicator" && (
          <select onChange={set("name")} className="border border-gray-300 rounded-md px-2 py-1.5 text-sm bg-white">
            <option value="">Tous les indicateurs</option>
            {(catalog?.indicators || []).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        )}
        {metric === "stocks" && (
          <select onChange={set("resource")} className="border border-gray-300 rounded-md px-2 py-1.5 text-sm bg-white">
            <option value="">Toutes les ressources</option>
            {(catalog?.resources || []).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        )}
        <label className="text-sm text-gray-600 flex items-center gap-1.5 ml-auto">
          <input type="checkbox" checked={showSites} onChange={(e) => setShowSites(e.target.checked)} />
          Afficher les sites (par état)
        </label>
      </div>

      <div id="map" className="h-[540px] rounded-lg border border-gray-200 z-0" />

      <div className="flex flex-wrap gap-6 text-sm bg-white border border-gray-200 rounded-lg p-3">
        <div className="flex items-center gap-2">
          <span className="text-gray-600">0</span>
          {RAMP.map((c) => (
            <span key={c} className="inline-block w-6 h-3 rounded-sm" style={{ background: c }} />
          ))}
          <span className="text-gray-600">{legendMax}</span>
        </div>
        {showSites && (
          <div className="flex items-center gap-4">
            {Object.entries(STATUS_COLORS).map(([k, c]) => (
              <span key={k} className="flex items-center gap-1.5 text-gray-600">
                <span className="inline-block w-3 h-3 rounded-full" style={{ background: c }} />
                {k.replace("_", " ")}
              </span>
            ))}
          </div>
        )}
      </div>
      <p className="text-xs text-gray-500">
        Frontières régionales simplifiées et indicatives (démonstration) — à
        remplacer par les géométries officielles COD-AB/OCHA.
      </p>
    </div>
  );
}
