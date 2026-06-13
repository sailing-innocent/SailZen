/**
 * Namespace for all graph related configurations.
 */
export type SailGraphConfig = {
  zoomSpeed: number;
  /**
   * If true, create a note if it hasn't been created already when clicked on a graph node
   */
  createStub: boolean;
};

/**
 * Generates default {@link SailGraphConfig}
 * @returns SailGraphConfig
 */
export function genDefaultGraphConfig(): SailGraphConfig {
  return {
    zoomSpeed: 1,
    createStub: false,
  };
}
