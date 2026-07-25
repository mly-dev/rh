import { useEffect, useState } from "react";
import { get } from "../api";

const STATUS_LABELS = {
  preview: ["Prévisualisé", "bg-gray-100 text-gray-700"],
  imported: ["Importé", "bg-green-100 text-green-800"],
  failed: ["Échec", "bg-red-100 text-red-800"],
};

export default function SourcesPage() {
  const [sources, setSources] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    get("/sources").then(setSources).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-red-600">Erreur : {error}</p>;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 overflow-x-auto">
      <h2 className="font-medium mb-3">Traçabilité des fichiers importés</h2>
      {sources.length === 0 ? (
        <p className="text-gray-500 text-sm">Aucun fichier importé pour l'instant.</p>
      ) : (
        <table className="text-sm min-w-full">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th className="py-2 pr-4">Fichier</th>
              <th className="py-2 pr-4">Type</th>
              <th className="py-2 pr-4">Domaine</th>
              <th className="py-2 pr-4">Téléversé par</th>
              <th className="py-2 pr-4">Date</th>
              <th className="py-2 pr-4">Lignes</th>
              <th className="py-2 pr-4">Statut</th>
              <th className="py-2 pr-4">Import</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => {
              const [label, cls] = STATUS_LABELS[s.status] || [s.status, ""];
              const imp = s.report?.import;
              return (
                <tr key={s.id} className="border-b border-gray-100">
                  <td className="py-2 pr-4 font-medium">{s.filename}</td>
                  <td className="py-2 pr-4 uppercase text-gray-500">{s.file_type}</td>
                  <td className="py-2 pr-4">{s.domain}</td>
                  <td className="py-2 pr-4">{s.uploaded_by}</td>
                  <td className="py-2 pr-4 text-gray-500">
                    {s.uploaded_at ? new Date(s.uploaded_at).toLocaleString("fr-FR") : ""}
                  </td>
                  <td className="py-2 pr-4">{s.row_count}</td>
                  <td className="py-2 pr-4">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${cls}`}>{label}</span>
                  </td>
                  <td className="py-2 pr-4 text-gray-600">
                    {imp
                      ? `${imp.accepted} ok / ${imp.rejected} rejetées (${s.report.entity})`
                      : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
