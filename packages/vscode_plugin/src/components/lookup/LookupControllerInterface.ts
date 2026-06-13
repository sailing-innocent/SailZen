import { DNodeType } from "@saili/common-all";
import { CancellationTokenSource } from "vscode";
import { SailBtn } from "./ButtonTypes";
import { ILookupProvider } from "./LookupProviderInterface";
import { SailQuickPicker } from "./types";

export type CreateQuickPickOpts = {
  title?: string;
  placeholder: string;
  /**
   * QuickPick.ignoreFocusOut prop
   */
  ignoreFocusOut?: boolean;
  /**
   * Initial value for quickpick
   */
  initialValue?: string;
  nonInteractive?: boolean;
  /**
   * See {@link SailQuickPicker["alwaysShow"]}
   */
  alwaysShow?: boolean;
  /**
   * if canSelectMany and items from selection, select all items at creation
   */
  selectAll?: boolean;
};

export type PrepareQuickPickOpts = CreateQuickPickOpts & {
  provider: ILookupProvider;
  onDidHide?: () => void;
};

export type ShowQuickPickOpts = {
  quickpick: SailQuickPicker;
  provider: ILookupProvider;
  nonInteractive?: boolean;
  fuzzThreshold?: number;
};

export interface ILookupController {
  readonly quickPick: SailQuickPicker;

  fuzzThreshold: number;

  readonly cancelToken: CancellationTokenSource;

  nodeType: DNodeType;

  readonly provider: ILookupProvider;

  /**
   * Wire up quickpick and initialize buttons
   */
  prepareQuickPick(
    opts: PrepareQuickPickOpts
  ): Promise<{ quickpick: SailQuickPicker }>;

  showQuickPick(opts: ShowQuickPickOpts): Promise<SailQuickPicker>;

  onHide(): void;

  show(
    opts: CreateQuickPickOpts & {
      /**
       * Don't show quickpick
       */
      nonInteractive?: boolean;
      /**
       * Initial value for quickpick
       */
      initialValue?: string;
      provider: ILookupProvider;
    }
  ): Promise<SailQuickPicker>;

  createCancelSource(): CancellationTokenSource;

  /**
   * Indicates that the journal button is pressed
   *
   * @deprecated - this is a temp solution; remove from interface once there's a
   * better way to trigger journal button functionality
   */
  isJournalButtonPressed(): boolean;
}

export interface ILookupControllerFactory {
  create(opts?: LookupControllerCreateOpts): ILookupController;
}

export type LookupControllerCreateOpts = {
  /**
   * Node type
   */
  nodeType: string;
  /**
   * Replace default buttons
   */
  buttons?: SailBtn[];
  /**
   * When true, don't enable vault selection
   */
  disableVaultSelection?: boolean;
  /**
   * if vault selection isn't disabled,
   * press button on init if true
   */
  vaultButtonPressed?: boolean;
  /** If vault selection isn't disabled, allow choosing the mode of selection.
   *  Defaults to true. */
  vaultSelectCanToggle?: boolean;
  /**
   * Additional buttons
   */
  extraButtons?: SailBtn[];
  /**
   * 0.0 = exact match
   * 1.0 = match anything
   */
  fuzzThreshold?: number;
  /**
   * enable lookup view - false by default or if undefined
   */
  enableLookupView?: boolean;
  /**
   * optional custom title of quickpic
   */
  title?: string;
};


