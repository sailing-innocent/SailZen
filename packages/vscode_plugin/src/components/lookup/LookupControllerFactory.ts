import {
  DNodeType,
  LookupNoteTypeEnum,
  LookupSelectionTypeEnum,
} from "@saili/common-all";
import _ from "lodash";
import { IDendronExtension } from "../../dendronExtensionInterface";
import { TwoWayBinding } from "../../utils/TwoWayBinding";
import { VaultSelectButton } from "./buttons";
import { LookupController } from "./LookupController";
import {
  ILookupController,
  ILookupControllerFactory,
  LookupControllerCreateOpts,
} from "./LookupControllerInterface";
import { VaultSelectionMode } from "./types";

export class LookupControllerFactory implements ILookupControllerFactory {
  private extension: IDendronExtension;

  constructor(extension: IDendronExtension) {
    this.extension = extension;
  }

  create(opts?: LookupControllerCreateOpts): ILookupController {
    const { vaults } = this.extension.getDWorkspace();

    // disable vault selection if explicitly requested or we are looking at schemas
    const disableVaultSelection =
      (_.isBoolean(opts?.disableVaultSelection) &&
        opts?.disableVaultSelection) ||
      opts?.nodeType === "schema";

    // --- start: multi vault selection check
    const isMultiVault = vaults.length > 1 && !disableVaultSelection;
    // should vault toggle be pressed?
    const maybeVaultSelectButtonPressed = _.isUndefined(
      opts?.vaultButtonPressed
    )
      ? isMultiVault
      : isMultiVault && opts!.vaultButtonPressed;

    const maybeVaultSelectButton =
      opts?.nodeType === "note" && isMultiVault
        ? [
            VaultSelectButton.create({
              pressed: maybeVaultSelectButtonPressed,
              canToggle: opts?.vaultSelectCanToggle,
            }),
          ]
        : [];
    // --- end: multi vault selection check
    const buttons = opts?.buttons || maybeVaultSelectButton;
    const extraButtons = opts?.extraButtons || [];

    const viewModel = {
      selectionState: new TwoWayBinding<LookupSelectionTypeEnum>(
        LookupSelectionTypeEnum.none
      ),
      vaultSelectionMode: new TwoWayBinding<VaultSelectionMode>(
        VaultSelectionMode.auto
      ),
      isMultiSelectEnabled: new TwoWayBinding<boolean>(false),
      isCopyNoteLinkEnabled: new TwoWayBinding<boolean>(false),
      isApplyDirectChildFilter: new TwoWayBinding<boolean>(false),
      nameModifierMode: new TwoWayBinding<LookupNoteTypeEnum>(
        LookupNoteTypeEnum.none
      ),
      isSplitHorizontally: new TwoWayBinding<boolean>(false),
    };

    return new LookupController({
      nodeType: opts?.nodeType as DNodeType,
      fuzzThreshold: opts?.fuzzThreshold,
      buttons: buttons.concat(extraButtons),
      enableLookupView: opts?.enableLookupView,
      title: opts?.title,
      viewModel,
    });
  }
}

