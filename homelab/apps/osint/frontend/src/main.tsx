import { createRoot } from "react-dom/client";
import "./globals.css";
import App from "./App";
import { AppErrorBoundary } from "./components/ErrorBoundary";

createRoot(document.getElementById("root")!).render(
    <AppErrorBoundary>
        <App />
    </AppErrorBoundary>
);
