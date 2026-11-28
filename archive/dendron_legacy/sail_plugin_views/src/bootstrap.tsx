import React from "react";
// import ReactDOM from "react-dom";
import { createRoot } from 'react-dom/client';
import SailApp, { SailAppProps } from "./components/SailApp";
import { SailComponent } from "./types";

function renderWithSailApp(props: SailAppProps) {
  return <SailApp {...props} />;
}

/**
 * Render standalone react app
 * @param opts.padding: override default padding
 */
export function renderOnDOM(
  Component: SailComponent,
  opts: SailAppProps["opts"]
) {
  const container = document.getElementById('root');
  if (!container) {
    throw new Error('No container found');
  }
  const root = createRoot(container);

  root.render(
    <React.StrictMode>
      {renderWithSailApp({ Component, opts })}
    </React.StrictMode>)
}
