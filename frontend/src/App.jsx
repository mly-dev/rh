import { NavLink, Route, Routes } from "react-router-dom";
import ImportPage from "./pages/ImportPage";
import MapPage from "./pages/MapPage";
import DashboardPage from "./pages/DashboardPage";
import AskPage from "./pages/AskPage";
import SourcesPage from "./pages/SourcesPage";

const tabs = [
  { to: "/", label: "Tableaux de bord", end: true },
  { to: "/carte", label: "Carte" },
  { to: "/import", label: "Import" },
  { to: "/question", label: "Question" },
  { to: "/sources", label: "Sources" },
];

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center gap-6">
          <div>
            <h1 className="font-semibold text-lg leading-tight">
              Plateforme de données · Niger
            </h1>
            <p className="text-xs text-gray-500">
              Données agrégées et d'infrastructures uniquement — aucune donnée
              personnelle
            </p>
          </div>
          <nav className="flex gap-1 flex-wrap">
            {tabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.end}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md text-sm font-medium ${
                    isActive
                      ? "bg-blue-600 text-white"
                      : "text-gray-600 hover:bg-gray-100"
                  }`
                }
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/carte" element={<MapPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/question" element={<AskPage />} />
          <Route path="/sources" element={<SourcesPage />} />
        </Routes>
      </main>
    </div>
  );
}
