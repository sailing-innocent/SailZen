import { ITelemetryClient } from "../common/ITelemetryClient";

/**
 * TODO: Not sure we actually need this implementation.
 */
export class NodeTelemetryClient implements ITelemetryClient {
  track(
    _event: string,
    _customProps?: any,
    _segmentProps?: { timestamp?: Date | undefined } | undefined
  ): Promise<void> {
    throw new Error("NodeTelemetryClient - Method not implemented.");
  }
  identify(): Promise<void> {
    throw new Error("NodeTelemetryClient - Method not implemented.");
  }
}
