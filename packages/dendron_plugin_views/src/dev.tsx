/**
 * Development entry point with mock data support
 * Use this for standalone component development and testing
 */

import React from "react";
import { createRoot } from "react-dom/client";
import { MockProvider } from "./mock";
import { mockPreviewHTML, mockNote, mockVault } from "./mock";
import { ideSlice } from "./features/ide";
import { combinedStore } from "./features";
import { LoadingStatus } from "./types";
import { DendronProps } from "./types/index";
import { EngineState } from "./features/engine/slice";
import { IDEState } from "./features/ide/slice";
import { GraphThemeEnum } from "@saili/common-all";
import "./styles/scss/main-plugin.scss";

// Static imports for components (Vite ESM doesn't support require())
import DendronNotePreview from "./components/DendronNotePreview";
import DendronCalendarPanel from "./components/DendronCalendarPanel";

// Component registry
const COMPONENTS: Record<string, React.ComponentType<DendronProps>> = {
  DendronNotePreview,
  DendronCalendarPanel,
};

const VALID_NAMES = Object.keys(COMPONENTS);

const elem = document.getElementById("root")!;
const VIEW_NAME = elem.getAttribute("data-name")!;
const IS_MOCK = elem.getAttribute("data-mock") === "true";

if (VALID_NAMES.includes(VIEW_NAME)) {
  console.log(`[Dev] Loading component: ${VIEW_NAME} (mock: ${IS_MOCK})`);

  // Get component from registry
  const View = COMPONENTS[VIEW_NAME];

  // Create mock engine state
  const mockEngine: EngineState = {
    notes: { [mockNote.id]: mockNote },
    notesRendered: { [mockNote.id]: mockPreviewHTML },
    vaults: [mockVault],
    schemas: {},
    noteFName: {},
    loading: LoadingStatus.IDLE,
    error: null,
    currentRequestId: undefined,
  };

  // Create mock IDE state
  const mockIde: IDEState = {
    noteActive: mockNote,
    notePrev: undefined,
    theme: "dark",
    graphStyles: "",
    views: {},
    seedsInWorkspace: undefined,
    lookupModifiers: undefined,
    tree: undefined,
    graphTheme: GraphThemeEnum.Classic,
    graphDepth: 1,
    showBacklinks: true,
    showOutwardLinks: true,
    showHierarchy: true,
    isLocked: false,
    previewHTML: mockPreviewHTML,
  };

  const mockWorkspace = {
    url: "http://localhost:3005",
    ws: "E:\\ws\\repos\\SailDendron\\test-workspace",
    browser: true,
    theme: "dark",
  };

  // Create props for the component
  const mockProps: DendronProps = {
    engine: mockEngine,
    ide: mockIde,
    workspace: mockWorkspace,
  };

  // Create a wrapper component that provides mock data
  function DevWrapper() {
    React.useEffect(() => {
      // Initialize store with mock data
      combinedStore.dispatch(ideSlice.actions.setNoteActive(mockNote));
      combinedStore.dispatch(ideSlice.actions.setPreviewHTML(mockPreviewHTML));
      combinedStore.dispatch(ideSlice.actions.setTheme("dark"));
    }, []);

    return <View {...mockProps} />;
  }

  const container = document.getElementById("root");
  if (!container) {
    throw new Error("No container found");
  }
  const root = createRoot(container);

  root.render(
    <React.StrictMode>
      <MockProvider>
        <DevWrapper />
      </MockProvider>
    </React.StrictMode>
  );
} else {
  console.error(
    `[Dev] Invalid component name: ${VIEW_NAME}. Valid names: ${VALID_NAMES.join(", ")}`
  );
}
