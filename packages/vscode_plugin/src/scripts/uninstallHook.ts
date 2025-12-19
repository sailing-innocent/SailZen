import { VSCodeEvents } from "@saili/common-all";
import { SegmentClient } from "@saili/common-server";

/**
 * Simple script to fire an uninstall analytics event during the
 * vscode:uninstall hook execution that runs after the extension has been
 * uninstalled. NOTE: AnalyticsUtils has been removed, so we use SegmentClient directly.
 */
async function main() {
  SegmentClient.instance().track({ event: VSCodeEvents.Uninstall });

  // Force an upload flush():
  SegmentClient.instance().identify();
}

main();
