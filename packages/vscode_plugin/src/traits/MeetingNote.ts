import {
  DendronConfig,
  NoteTrait,
  OnCreateContext,
  onWillCreateProps,
  SetNameModifierResp,
} from "@saili/common-all";
import { DendronClientUtils } from "../clientUtils";
import { IDendronExtension } from "../dendronExtensionInterface";

export class MeetingNote implements NoteTrait {
  id: string = "meetingNote";
  getTemplateType: any;

  _config: DendronConfig;
  _ext: IDendronExtension;
  _noConfirm: boolean = false;

  constructor(
    config: DendronConfig,
    ext: IDendronExtension,
    noConfirm?: boolean
  ) {
    this._config = config;
    this._ext = ext;
    this._noConfirm = noConfirm ?? this._noConfirm;
  }

  get OnWillCreate(): onWillCreateProps {
    const promptUserForModification = !this._noConfirm;
    return {
      setNameModifier(this, _opts: OnCreateContext): SetNameModifierResp {
        const name = DendronClientUtils.getMeetingNoteName();

        return { name, promptUserForModification };
      },
    };
  }
}

