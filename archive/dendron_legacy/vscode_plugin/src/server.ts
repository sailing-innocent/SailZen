/**
 * This file is used by {@link startServerProcess} to start the sail engine in a separate process
 */
import { ServerUtils } from "@saili/api-server";
import { stringifyError } from "@saili/common-all";

(async () => {
  // Register the sail_server-backed weather page element providers in this
  // (prod-mode) engine child process. Page element rendering happens inside
  // the engine process, so the extension-host registration in _extension.ts
  // does not cover prod mode. weatherCore is vscode-free and safe to bundle.
  // Silent degradation: a registration failure must not break engine startup.
  try {
    const { createWeatherCore } = await import(
      "./features/pageElements/weatherCore"
    );
    const { getDefaultPageElementRegistry, renderPageElementHelp } =
      await import("@saili/unified");
    createWeatherCore({
      resolveBaseUrl: () =>
        process.env.SAIL_SERVER_URL ?? "http://localhost:1974",
      renderPrefixHelp: (ctx) =>
        renderPageElementHelp({
          key: "PREFIX",
          raw: ctx.raw,
          providers: getDefaultPageElementRegistry().list(),
        }),
    }).register(getDefaultPageElementRegistry());
  } catch {
    // ignore: weather elements degrade to the built-in help content
  }

  try {
    const { createRhythmCore } = await import(
      "./features/pageElements/rhythmCore"
    );
    const { getDefaultPageElementRegistry, renderPageElementHelp } =
      await import("@saili/unified");
    createRhythmCore({
      resolveBaseUrl: () =>
        process.env.SAIL_SERVER_URL ?? "http://localhost:1974",
      renderPrefixHelp: (ctx) =>
        renderPageElementHelp({
          key: "RHYTHM_PREFIX",
          raw: ctx.raw,
          providers: getDefaultPageElementRegistry().list(),
        }),
    }).register(getDefaultPageElementRegistry());
  } catch {
    // ignore: rhythm elements degrade to the built-in help content
  }

  try {
    // run forever
    await ServerUtils.startServerNode(ServerUtils.prepareServerArgs());
  } catch (err: any) {
    if (process.send) {
      process.send(stringifyError(err));
    }
    process.exit(1);
  }
})();
