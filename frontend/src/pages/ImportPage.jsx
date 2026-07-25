import { useEffect, useState } from "react";
import { get, post, upload } from "../api";

const DOMAINS = [
  ["humanitaire", "Humanitaire / ONG"],
  ["gouvernemental", "Gouvernemental"],
  ["commercial", "Commercial / PME"],
  ["autre", "Autre"],
];

export default function ImportPage() {
  const [ontology, setOntology] = useState(null);
  const [file, setFile] = useState(null);
  const [uploadedBy, setUploadedBy] = useState("");
  const [domain, setDomain] = useState("autre");
  const [result, setResult] = useState(null); // réponse de l'upload (preview…)
  const [entity, setEntity] = useState("site");
  const [mappings, setMappings] = useState({});
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    get("/ontology").then(setOntology).catch(() => {});
  }, []);

  async function doUpload(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setReport(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("uploaded_by", uploadedBy || "anonyme");
      fd.append("domain", domain);
      const res = await upload("/uploads", fd);
      setResult(res);
      const firstEntity = Object.keys(res.suggestions || {}).find(
        (ent) => Object.keys(res.suggestions[ent]).length > 0
      );
      const chosen = firstEntity || "site";
      setEntity(chosen);
      setMappings(res.suggestions?.[chosen] || {});
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function changeEntity(ent) {
    setEntity(ent);
    setMappings(result?.suggestions?.[ent] || {});
  }

  async function doImport() {
    setBusy(true);
    setError("");
    try {
      const clean = Object.fromEntries(
        Object.entries(mappings).filter(([, v]) => v)
      );
      const res = await post(`/uploads/${result.source.id}/import`, {
        entity,
        mappings: clean,
      });
      setReport(res.report);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const blocked = new Set(
    (result?.pii_alerts || []).filter((a) => a.level === "block").map((a) => a.column)
  );
  const fields = ontology?.[entity]?.fields || {};

  return (
    <div className="space-y-4 max-w-5xl">
      <form onSubmit={doUpload} className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
        <h2 className="font-medium">1. Téléverser un fichier (CSV, Excel, PDF)</h2>
        <div className="flex flex-wrap gap-3 items-center">
          <input
            type="file"
            accept=".csv,.xlsx,.xls,.pdf"
            onChange={(e) => setFile(e.target.files[0])}
            className="text-sm"
          />
          <input
            type="text"
            placeholder="Votre nom / organisation"
            value={uploadedBy}
            onChange={(e) => setUploadedBy(e.target.value)}
            className="border border-gray-300 rounded-md px-2 py-1.5 text-sm"
          />
          <select value={domain} onChange={(e) => setDomain(e.target.value)}
                  className="border border-gray-300 rounded-md px-2 py-1.5 text-sm bg-white">
            {DOMAINS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button
            type="submit"
            disabled={!file || busy}
            className="bg-blue-600 text-white px-4 py-1.5 rounded-md text-sm font-medium disabled:opacity-50"
          >
            {busy ? "Analyse…" : "Analyser"}
          </button>
        </div>
      </form>

      {error && <p className="text-red-600 bg-red-50 border border-red-200 rounded-lg p-3 text-sm">{error}</p>}

      {result && (
        <>
          {result.pii_alerts?.length > 0 && (
            <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 space-y-2">
              <h3 className="font-medium text-amber-900">
                ⚠ Garde-fou : données personnelles détectées
              </h3>
              {result.pii_alerts.map((a) => (
                <p key={a.column} className="text-sm text-amber-900">
                  <strong>{a.column}</strong> — {a.reason}{" "}
                  <span className="text-amber-700">{a.suggestion}</span>
                </p>
              ))}
              <p className="text-xs text-amber-700">
                Ces colonnes sont exclues : elles ne peuvent ni être mappées ni
                être importées comme propriétés.
              </p>
            </div>
          )}

          <div className="bg-white border border-gray-200 rounded-lg p-4 overflow-x-auto">
            <h2 className="font-medium mb-2">
              2. Prévisualisation — {result.preview.row_count} lignes
            </h2>
            <table className="text-sm min-w-full">
              <thead>
                <tr className="border-b border-gray-200 text-left">
                  {result.preview.columns.map((c) => (
                    <th key={c.name} className={`py-1.5 pr-4 font-medium ${blocked.has(c.name) ? "text-red-500 line-through" : ""}`}>
                      {c.name}
                      <span className="block text-xs font-normal text-gray-400">{c.type}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.preview.rows.slice(0, 8).map((row, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    {result.preview.columns.map((c) => (
                      <td key={c.name} className="py-1 pr-4 text-gray-700">
                        {blocked.has(c.name) ? "•••" : String(row[c.name] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
            <h2 className="font-medium">3. Mapping vers l'ontologie</h2>
            <div className="flex gap-2 flex-wrap">
              {Object.entries(ontology || {}).map(([key, ent]) => (
                <button
                  key={key}
                  onClick={() => changeEntity(key)}
                  className={`px-3 py-1.5 rounded-md text-sm border ${
                    entity === key
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  {ent.label}
                </button>
              ))}
            </div>
            <p className="text-sm text-gray-500">{ontology?.[entity]?.description}</p>
            <div className="grid sm:grid-cols-2 gap-2">
              {result.preview.columns
                .filter((c) => !blocked.has(c.name))
                .map((c) => (
                  <label key={c.name} className="flex items-center gap-2 text-sm">
                    <span className="w-40 truncate text-gray-700">{c.name}</span>
                    <span className="text-gray-400">→</span>
                    <select
                      value={mappings[c.name] || ""}
                      onChange={(e) =>
                        setMappings((m) => ({ ...m, [c.name]: e.target.value }))
                      }
                      className="border border-gray-300 rounded-md px-2 py-1 bg-white flex-1"
                    >
                      <option value="">(propriété additionnelle)</option>
                      {Object.entries(fields).map(([f, spec]) => (
                        <option key={f} value={f}>
                          {spec.label}
                          {spec.required ? " *" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
            </div>
            <button
              onClick={doImport}
              disabled={busy || result.source.status === "imported"}
              className="bg-green-700 text-white px-4 py-1.5 rounded-md text-sm font-medium disabled:opacity-50"
            >
              {busy ? "Import…" : "4. Importer"}
            </button>
          </div>
        </>
      )}

      {report && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
          <h2 className="font-medium">Rapport d'import</h2>
          <p className="text-sm">
            <span className="text-green-700 font-medium">{report.accepted} acceptée(s)</span>
            {" · "}
            <span className={report.rejected ? "text-red-600 font-medium" : "text-gray-500"}>
              {report.rejected} rejetée(s)
            </span>
          </p>
          {report.rejects.length > 0 && (
            <ul className="text-sm text-gray-600 list-disc pl-5">
              {report.rejects.slice(0, 10).map((r, i) => (
                <li key={i}>Ligne {r.row} : {r.reason}</li>
              ))}
            </ul>
          )}
          {report.warnings.length > 0 && (
            <ul className="text-sm text-amber-700 list-disc pl-5">
              {report.warnings.slice(0, 10).map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
