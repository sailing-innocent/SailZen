import {
  SailConfig,
  NoteTrait,
  OnCreateContext,
  onWillCreateProps,
  SetNameModifierResp,
} from "@saili/common-all";
import { SailClientUtils } from "../clientUtils";
import { ISailExtension } from "../sailExtensionInterface";

export class MeetingNote implements NoteTrait {
  id: string = "meetingNote";
  getTemplateType: any;

  _config: SailConfig;
  _ext: ISailExtension;
  _noConfirm: boolean = false;

  constructor(
    config: SailConfig,
    ext: ISailExtension,
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
        const name = SailClientUtils.getMeetingNoteName();

        return { name, promptUserForModification };
      },
    };
  }
}

