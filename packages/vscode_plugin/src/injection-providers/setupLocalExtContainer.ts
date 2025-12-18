import "reflect-metadata";
import { DVault, EngineEventEmitter } from "@saili/common-all";
import { container } from "tsyringe";
import * as vscode from "vscode";
import { EngineAPIService } from "../services/EngineAPIService";
import { MetadataSvcTreeViewConfig } from "../views/node/treeview/MetadataSvcTreeViewConfig";
import { ITreeViewConfig } from "../views/common/treeview/ITreeViewConfig";
import { EngineNoteProvider } from "../views/common/treeview/EngineNoteProvider";
import { WSUtilsWeb } from "../web/utils/WSUtils";

export async function setupLocalExtContainer(opts: {
  wsRoot: string;
  vaults: DVault[];
  engine: EngineAPIService;
}) {
  const { wsRoot, engine, vaults } = opts;
  container.register<EngineEventEmitter>("EngineEventEmitter", {
    useToken: "ReducedDEngine",
  });
  container.register("wsRoot", { useValue: vscode.Uri.file(wsRoot) });
  container.register("ReducedDEngine", { useValue: engine });
  container.register("vaults", { useValue: vaults });
  container.register<ITreeViewConfig>("ITreeViewConfig", {
    useClass: MetadataSvcTreeViewConfig,
  });
  // Register tree view related classes
  container.register(EngineNoteProvider, { useClass: EngineNoteProvider });
  container.register(WSUtilsWeb, { useClass: WSUtilsWeb });
}
