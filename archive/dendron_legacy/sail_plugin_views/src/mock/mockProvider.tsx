/**
 * Mock Provider for standalone development
 * Simulates VSCode environment and provides mock data
 */

import React, { useEffect } from "react";
import { Provider } from "react-redux";
import { combinedStore } from "../features";
import { ideSlice } from "../features/ide";
import { mockNote, mockPreviewHTML } from "./mockData";

interface MockProviderProps {
  children: React.ReactNode;
}

/**
 * Wraps children with mock Redux store and simulates VSCode messages
 */
export function MockProvider({ children }: MockProviderProps) {
  useEffect(() => {
    // Simulate initial VSCode message after component mounts
    const timer = setTimeout(() => {
      // Dispatch mock data to the store
      combinedStore.dispatch(ideSlice.actions.setNoteActive(mockNote));
      combinedStore.dispatch(ideSlice.actions.setPreviewHTML(mockPreviewHTML));
      combinedStore.dispatch(ideSlice.actions.setTheme("dark"));
    }, 100);

    return () => clearTimeout(timer);
  }, []);

  return <Provider store={combinedStore}>{children}</Provider>;
}

/**
 * Hook to check if running in mock mode
 */
export function useMockMode(): boolean {
  const elem = document.getElementById("root");
  return elem?.getAttribute("data-mock") === "true";
}
