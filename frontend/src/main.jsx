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
import "./logo-animation.css";
import "./readability.css";
import "./explainability.css";
import "./auth.css";
import "./garmin-connection.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
