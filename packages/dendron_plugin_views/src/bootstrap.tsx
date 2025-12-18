import React from "react";
// import ReactDOM from "react-dom";
import { createRoot } from 'react-dom/client';
import DendronApp, { DendronAppProps } from "./components/DendronApp";
import { DendronComponent } from "./types";

function renderWithDendronApp(props: DendronAppProps) {
  return <DendronApp {...props} />;
}

/**
 * Render standalone react app
 * @param opts.padding: override default padding
 */
export function renderOnDOM(
  Component: DendronComponent,
  opts: DendronAppProps["opts"]
) {
  const container = document.getElementById('root');
  if (!container) {
    throw new Error('No container found');
  }
  const root = createRoot(container);

  root.render(
    <React.StrictMode>
      {renderWithDendronApp({ Component, opts })}
    </React.StrictMode>)
}
