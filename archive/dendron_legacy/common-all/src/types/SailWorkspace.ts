import { DVault } from "./DVault";
import { RemoteEndpoint } from "./RemoteEndpoint";

export type SailWorkspace = {
  name: string;
  vaults: DVault[];
  remote: RemoteEndpoint;
};
