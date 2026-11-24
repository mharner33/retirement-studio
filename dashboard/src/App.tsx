import { useEffect, useState } from "react";
import { getJson } from "./api";
import { ProfilePage } from "./pages/ProfilePage";
import { applyTheme, initialTheme, type Theme } from "./theme";

type Page = "status" | "profile";
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
          {(["status", "profile"] as const).map((p) => (
            <button
              key={p}
              type="button"
              className={p === page ? "nav-item selected" : "nav-item"}
              aria-current={p === page ? "page" : undefined}
              onClick={() => {
                setPage(p);
              }}
            >
              {p === "status" ? "Status" : "Profile"}
            </button>
          ))}
        </nav>
        <button type="button" className="primary" onClick={toggleTheme}>
          {theme === "light" ? "Dark theme" : "Light theme"}
        </button>
      </aside>
      <main className="content">
        {page === "status" ? (
          <section className="card">
            <h2>Status</h2>
            <p className="secondary" role="status">
              {STATUS_TEXT[health]}
            </p>
          </section>
        ) : (
          <ProfilePage />
        )}
      </main>
    </div>
  );
}
