/**
 * OSINT Platform — Dashboard Shell
 *
 * This is the application shell. The full dashboard UI (graph visualization,
 * investigation management, search) will be built out in subsequent iterations.
 */

function App() {
    return (
        <div style={{ fontFamily: "Inter, sans-serif", color: "#e2e8f0", background: "#0f172a", minHeight: "100vh" }}>
            <header style={{ padding: "1.5rem 2rem", borderBottom: "1px solid #1e293b", display: "flex", alignItems: "center", gap: "1rem" }}>
                <h1 style={{ fontSize: "1.25rem", fontWeight: 600, margin: 0 }}>
                    🔍 OSINT Platform
                </h1>
                <span style={{ fontSize: "0.75rem", background: "#1e293b", padding: "0.25rem 0.75rem", borderRadius: "9999px", color: "#94a3b8" }}>
                    v0.1.0
                </span>
            </header>

            <main style={{ padding: "2rem", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "calc(100vh - 80px)" }}>
                <div style={{ textAlign: "center", maxWidth: "480px" }}>
                    <h2 style={{ fontSize: "1.5rem", fontWeight: 500, marginBottom: "1rem" }}>
                        Platform Initialized
                    </h2>
                    <p style={{ color: "#94a3b8", lineHeight: 1.6 }}>
                        The OSINT platform backend is running. The full dashboard with
                        Sigma.js graph visualization, investigation management, and
                        real-time analysis feeds will be built in the next phase.
                    </p>
                    <a
                        href="/api/docs"
                        style={{ display: "inline-block", marginTop: "1.5rem", padding: "0.75rem 1.5rem", background: "#3b82f6", color: "#fff", borderRadius: "0.5rem", textDecoration: "none", fontWeight: 500 }}
                    >
                        Open API Documentation →
                    </a>
                </div>
            </main>
        </div>
    );
}

export default App;
