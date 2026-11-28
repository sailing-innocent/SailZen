import {
  ConfigUtils,
  SailConfig,
  LookupNoteTypeEnum,
  NoteTrait,
  NoteUtils,
  OnCreateContext,
  onCreateProps,
  SetNameModifierResp,
} from "@saili/common-all";
import { SailClientUtils } from "../clientUtils";

export class JournalNote implements NoteTrait {
  id: string = "journalNote";
  getTemplateType: any;

  _config: SailConfig;

  constructor(config: SailConfig) {
    this._config = config;
  }

  get OnWillCreate() {
    const config = this._config;

    return {
      setNameModifier(this, _opts: OnCreateContext): SetNameModifierResp {
        const journalConfig = ConfigUtils.getJournal(config);
        // const dailyJournalDomain = journalConfig.dailyDomain;

        const { noteName: fname } = SailClientUtils.genNoteName(
          LookupNoteTypeEnum.journal,
          {
            overrides: { domain: journalConfig.name },
          }
        );

        return { name: fname, promptUserForModification: false };
      },
    };
  }

  get OnCreate(): onCreateProps {
    const config = this._config;

    return {
      setTitle(opts: OnCreateContext): string {
        const journalConfig = ConfigUtils.getJournal(config);
        // Use journalConfig.dailyDomain ('daily')
        // because fname is 'journal.daily.2025.12.24', we need to find date after 'daily'
        const journalName = journalConfig.dailyDomain;
        const title = NoteUtils.genJournalNoteTitle({
          fname: opts.currentNoteName!,
          journalName,
        });

        return title;
      },
    };
  }
}

