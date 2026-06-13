import { EngineState } from "../features/engine/slice";
import { IDEState } from "../features/ide/slice";

export type WorkspaceProps = {
  url: string;
  ws: string;
  theme?: string;
  browser?: boolean;
};

export type SailComponent = React.FunctionComponent<SailProps>;

export type SailProps = {
  engine: EngineState;
  ide: IDEState;
  workspace: WorkspaceProps;
  isSidePanel?: boolean;
};
