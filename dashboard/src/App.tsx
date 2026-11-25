import { useEffect, useState } from "react";
import { getJson } from "./api";
import { PlanPage } from "./pages/PlanPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RulesPage } from "./pages/RulesPage";
import { StatementsPage } from "./pages/StatementsPage";
import { applyTheme, initialTheme, type Theme } from "./theme";

type Page = "status" | "profile" | "plan" | "rules" | "statements";

const PAGES: { id: Page; label: string }[] = [
  { id: "status", label: "Status" },
  { id: "profile", label: "Profile" },
  { id: "plan", label: "Plan" },
  { id: "rules", label: "Rules" },
  { id: "statements", label: "Statements" },
];
type Health = "checking" | "up" | "down";

const STATUS_TEXT: Record<Health, string> = {
  checking: "Checking backend",
  up: "Backend is up",
  down: "Backend is down",
};

export function App() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [page, setPage] = useState<Page>("status");
  const [health, setHealth] = useState<Health>("checking");

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    getJson<{ status: string }>("/api/health").then(
      () => {
        setHealth("up");
      },
      () => {
        setHealth("down");
      },
    );
  }, []);

  function toggleTheme(): void {
    const next: Theme = theme === "light" ? "dark" : "light";
    try {
      localStorage.setItem("theme", next);
    } catch {
      // storage unavailable, the choice lasts for this visit only
    }
    setTheme(next);
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <h1 className="brand">Retirement Studio</h1>
        <nav aria-label="Pages">
          {PAGES.map((p) => (
            <button
              key={p.id}
              type="button"
              className={p.id === page ? "nav-item selected" : "nav-item"}
              aria-current={p.id === page ? "page" : undefined}
              onClick={() => {
                setPage(p.id);
              }}
            >
              {p.label}
            </button>
          ))}
        </nav>
        <button type="button" className="primary" onClick={toggleTheme}>
          {theme === "light" ? "Dark theme" : "Light theme"}
        </button>
      </aside>
      <main className="content">
        {page === "status" && (
          <section className="card">
            <h2>Status</h2>
            <p className="secondary" role="status">
              {STATUS_TEXT[health]}
            </p>
          </section>
        )}
        {page === "profile" && <ProfilePage />}
        {page === "plan" && <PlanPage />}
        {page === "rules" && <RulesPage />}
        {page === "statements" && <StatementsPage />}
      </main>
    </div>
  );
}
