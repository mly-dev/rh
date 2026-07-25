import { useEffect, useState } from "react";
import { get, post } from "../api";

const EXAMPLES = [
  "Combien de centres de santé fonctionnels à Tillabéri ?",
  "Évolution des stocks de vivres à Diffa ?",
  "Combien d'incidents à Tillabéri ?",
  "Quel est le total des bénéficiaires à Maradi ?",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadHistory = () => get("/ask/history").then(setHistory).catch(() => {});
  useEffect(() => {
    loadHistory();
  }, []);

  async function ask(q) {
    const text = (q ?? question).trim();
    if (!text) return;
    setBusy(true);
    setError("");
    setResponse(null);
    try {
      const res = await post("/ask", { question: text });
      setResponse({ question: text, ...res });
      loadHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-4">
      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
        <h2 className="font-medium">Posez une question sur les données</h2>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="Ex : Combien de centres de santé fonctionnels à Tillabéri ?"
            className="border border-gray-300 rounded-md px-3 py-2 text-sm flex-1"
          />
          <button
            onClick={() => ask()}
            disabled={busy}
            className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium disabled:opacity-50"
          >
            {busy ? "…" : "Demander"}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setQuestion(ex);
                ask(ex);
              }}
              className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-full px-3 py-1"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {response && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          <p className="text-sm text-gray-500">{response.question}</p>
          <p className="text-base">{response.answer}</p>
          {response.steps?.length > 0 && (
            <details className="text-sm text-gray-600">
              <summary className="cursor-pointer text-gray-500">
                Requêtes exécutées ({response.steps.length})
              </summary>
              <ul className="mt-2 space-y-1 font-mono text-xs">
                {response.steps.map((s, i) => (
                  <li key={i} className="bg-gray-50 rounded p-2">
                    {s.function}({JSON.stringify(s.args)})
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {history.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="font-medium text-sm mb-2">Questions récentes</h3>
          <ul className="space-y-2">
            {history.slice(0, 8).map((h) => (
              <li key={h.id} className="text-sm border-b border-gray-100 pb-2">
                <p className="text-gray-500">{h.question}</p>
                <p className="text-gray-800">{h.answer}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
