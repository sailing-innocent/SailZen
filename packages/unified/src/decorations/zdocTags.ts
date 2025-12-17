import {
  position2VSCodeRange,
  ConfigUtils,
  DendronConfig,
  ReducedDEngine,
  TaskNoteUtils,
  VaultUtils,
  VSRange,
} from "@saili/common-all";
import { ZDocTag } from "../types";
import { Decorator } from "./utils";
import { DecorationWikilink, linkedNoteType } from "./wikilinks";

export const decorateZDocTag: Decorator<ZDocTag, DecorationWikilink> = async (
  opts
) => {
  const { node: zdocTag, engine, config } = opts;
  const position = zdocTag.position;

  const { type, errors } = await linkedNoteType({
    fname: zdocTag.fname,
    engine,
    vaults: config.workspace?.vaults ?? [],
  });

  const decoration: DecorationWikilink = {
    type,
    range: position2VSCodeRange(position),
  };

  return {
    decorations: [decoration],
    errors,
  };
};
