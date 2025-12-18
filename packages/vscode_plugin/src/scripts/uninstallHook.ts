import { VSCodeEvents } from "@saili/common-all";
import { SegmentClient } from "@saili/common-server";

/**
 * Simple script to fire an uninstall analytics event during the
 * vscode:uninstall hook execution that runs after the extension has been
 * uninstalled. NOTE: we cannot use @see {@link AnalyticsUtils}, as that
 * requires vscode, which is unavailable during the execution of the uninstall
 * hook.
 */
async function main() {
  SegmentClient.instance().track({ event: VSCodeEvents.Uninstall });

  // Force an upload flush():
  SegmentClient.instance().identify();
}

main();
