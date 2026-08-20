import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.jsx";
import "./styles.css";
import "./personalization.css";
import "./profile.css";
import "./calendar-plan.css";
import "./checkin.css";
import "./journal-feedback.css";
import "./trend-history.css";
import "./goal-readiness.css";
import "./brand.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
