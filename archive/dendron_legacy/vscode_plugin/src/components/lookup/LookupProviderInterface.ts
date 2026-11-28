import { SailQuickPicker } from "./types";
import { CancellationToken, CancellationTokenSource } from "vscode";
import {
  DNodePropsQuickInput,
  InvalidFilenameReason,
  NoteQuickInput,
  RespV2,
  SchemaQuickInput,
} from "@saili/common-all";

export type ILookupProvider = {
  id: string;
  provide: (opts: ProvideOpts) => Promise<void>;
  onUpdatePickerItems: (opts: OnUpdatePickerItemsOpts) => Promise<void>;
  registerOnAcceptHook: (hook: OnAcceptHook) => void;
  onDidAccept(opts: {
    quickpick: SailQuickPicker;
    cancellationToken: CancellationTokenSource;
  }): any;
  shouldRejectItem?: (opts: { item: NoteQuickInput }) =>
    | {
      shouldReject: true;
      reason: InvalidFilenameReason;
    }
    | {
      shouldReject: false;
      reason?: never;
    };
};

export interface INoteLookupProviderFactory {
  create(id: string, opts: ILookupProviderOpts): ILookupProvider;
}

export interface ISchemaLookupProviderFactory {
  create(id: string, opts: ILookupProviderOpts): ILookupProvider;
}

export type ProvideOpts = {
  quickpick: SailQuickPicker;
  token: CancellationTokenSource;
  fuzzThreshold: number;
};

export type OnUpdatePickerItemsOpts = {
  picker: SailQuickPicker;
  token?: CancellationToken;
  fuzzThreshold?: number;
  /**
   * force update even if picker vaule didn't change
   */
  forceUpdate?: boolean;
};

export type ILookupProviderOpts = {
  /**
   * should provide `Create New`
   */
  allowNewNote: boolean;
  /**
   * should provide `Create New with Template`
   * `allowNewNote` must be true for this to take effect.
   * false by default.
   */
  allowNewNoteWithTemplate?: boolean;
  noHidePickerOnAccept?: boolean;
  /** Forces to use picker value as is when constructing the query string. */
  forceAsIsPickerValueUsage?: boolean;
  /**
   * Extra items to show in picker.
   * This will always be shown at the top
   * when (and only when) nothing is queried.
   */
  extraItems?: DNodePropsQuickInput[];
  preAcceptValidators?: ((selectedItems: NoteQuickInput[]) => boolean)[];
};

export type NoteLookupProviderSuccessResp<T = never> = {
  selectedItems: readonly NoteQuickInput[];
  onAcceptHookResp: T[];
  cancel?: boolean;
};
export type NoteLookupProviderChangeStateResp = {
  action: "hide";
};

export type SchemaLookupProviderSuccessResp<T = never> = {
  selectedItems: readonly SchemaQuickInput[];
  onAcceptHookResp: T[];
  cancel?: boolean;
};

export type OnAcceptHook = (opts: {
  quickpick: SailQuickPicker;
  selectedItems: NoteQuickInput[];
}) => Promise<RespV2<any>>;



