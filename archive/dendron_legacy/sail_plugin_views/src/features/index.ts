import { getStage } from "@saili/common-all";
import { engineSlice } from "./engine/slice";
import { configureStore, Middleware } from "@reduxjs/toolkit";
import { ideSlice } from "./ide/slice";
// Import redux-logger statically (only used in dev mode)
import { createLogger } from "redux-logger";

export * from "./engine";
export * from "./ide";

const middleware: Middleware[] = [];

// Only add logger in development mode
if (getStage() === "dev") {
  const logger = createLogger({
    collapsed: true,
  });
  middleware.push(logger as Middleware);
}

const engine = engineSlice.reducer;
const ide = ideSlice.reducer;

const store = configureStore({
  reducer: {
    engine,
    ide,
  },
  middleware: (getDefaultMiddleware) => {
    const defaultMiddleware = getDefaultMiddleware();
    return [...defaultMiddleware, ...middleware];
  },
});

export { store as combinedStore };
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
export type { RootState as CombinedRootState };
export type { AppDispatch as CombinedDispatch };
