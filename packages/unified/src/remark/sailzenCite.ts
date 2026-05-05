import { DendronError } from "@saili/common-all";
import type { Plugin, Processor } from "unified";
import type {
  Extension as MicromarkExtension,
  Tokenizer,
  State,
  Effects,
  Code,
} from "micromark-util-types";
import type {
  Extension as FromMarkdownExtension,
  Handle,
} from "mdast-util-from-markdown";
import type {
  Options as ToMarkdownExtension,
  Handle as ToMarkdownHandle,
} from "mdast-util-to-markdown";
import { DendronASTDest, DendronASTTypes, SailZenCite } from "../types";
import { MDUtilsV5 } from "..";

/**
 * Remark plugin for SailZen ::cite[keys] directive.
 *
 * Parses inline citations like:
 *   ::cite[foo, bar]
 *   ::cite[ foo , bar ]
 *
 * And produces a sailzenCite AST node.
 */

export const CITE_REGEX = /^::cite\[([^\]]*)\]/;

// Character codes
const codes = {
  colon: 58,
  c: 99,
  i: 105,
  t: 116,
  e: 101,
  openBracket: 91,
  closeBracket: 93,
};

/**
 * Micromark syntax extension for ::cite[keys]
 */
function createSailzenCiteSyntax(): MicromarkExtension {
  const tokenizeSailzenCite: Tokenizer = function (
    effects: Effects,
    ok: State,
    nok: State
  ) {
    return start;

    function start(code: Code): State | undefined {
      if (code !== codes.colon) return nok(code);
      effects.enter("sailzenCite" as any);
      effects.enter("sailzenCiteMarker" as any);
      effects.consume(code);
      return secondColon;
    }

    function secondColon(code: Code): State | undefined {
      if (code !== codes.colon) return nok(code);
      effects.consume(code);
      effects.exit("sailzenCiteMarker" as any);
      effects.enter("sailzenCiteKeyword" as any);
      return keywordC;
    }

    function keywordC(code: Code): State | undefined {
      if (code !== codes.c) return nok(code);
      effects.consume(code);
      return keywordI;
    }

    function keywordI(code: Code): State | undefined {
      if (code !== codes.i) return nok(code);
      effects.consume(code);
      return keywordT;
    }

    function keywordT(code: Code): State | undefined {
      if (code !== codes.t) return nok(code);
      effects.consume(code);
      return keywordE;
    }

    function keywordE(code: Code): State | undefined {
      if (code !== codes.e) return nok(code);
      effects.consume(code);
      effects.exit("sailzenCiteKeyword" as any);
      return openBracket;
    }

    function openBracket(code: Code): State | undefined {
      if (code !== codes.openBracket) return nok(code);
      effects.consume(code);
      effects.enter("sailzenCiteContent" as any);
      return insideContent;
    }

    function insideContent(code: Code): State | undefined {
      if (code === null || code === codes.closeBracket) {
        effects.exit("sailzenCiteContent" as any);
        return closeBracket;
      }
      effects.consume(code);
      return insideContent;
    }

    function closeBracket(code: Code): State | undefined {
      if (code !== codes.closeBracket) return nok(code);
      effects.consume(code);
      effects.exit("sailzenCite" as any);
      return ok(code);
    }
  };

  return {
    text: {
      [codes.colon]: {
        tokenize: tokenizeSailzenCite,
      },
    },
  };
}

/**
 * mdast-util-from-markdown extension
 * Converts micromark tokens to mdast nodes
 */
function createFromMarkdownExtension(): FromMarkdownExtension {
  const enterSailzenCite: Handle = function (token) {
    this.enter(
      {
        type: DendronASTTypes.SAILZEN_CITE,
        keys: [],
      } as any,
      token
    );
  };

  const exitSailzenCiteContent: Handle = function (token) {
    const content = this.sliceSerialize(token);
    const node = this.stack[this.stack.length - 1] as unknown as SailZenCite;
    node.keys = content
      .split(/,\s*/)
      .map((s: string) => s.trim())
      .filter(Boolean);
  };

  const exitSailzenCite: Handle = function (token) {
    this.exit(token);
  };

  return {
    enter: {
      sailzenCite: enterSailzenCite,
    },
    exit: {
      sailzenCiteContent: exitSailzenCiteContent,
      sailzenCite: exitSailzenCite,
    },
  };
}

function getDest(proc: Processor): DendronASTDest {
  const procData = MDUtilsV5.getProcData(proc);
  if (procData.dest) return procData.dest;
  const directDest = (proc.data() as any).dest;
  if (directDest) return directDest;
  return DendronASTDest.MD_DENDRON;
}

/**
 * mdast-util-to-markdown extension
 * Converts mdast nodes back to markdown
 */
function createToMarkdownExtension(proc: Processor): ToMarkdownExtension {
  const handleSailzenCite: ToMarkdownHandle = function (
    node,
    _parent,
    _state,
    _info
  ) {
    const citeNode = node as unknown as SailZenCite;
    const dest = getDest(proc);
    const keys = citeNode.keys.join(", ");
    switch (dest) {
      case DendronASTDest.MD_DENDRON:
      case DendronASTDest.MD_REGULAR:
        return `::cite[${keys}]`;
      case DendronASTDest.HTML:
        return `<sup>[${keys}]</sup>`;
      case DendronASTDest.DOC_EXPORT:
        return `__CITE__[${keys}]`;
      case DendronASTDest.DOC_PREVIEW:
        return `<sup class="sailzen-cite">[${keys}]</sup>`;
      default:
        throw new DendronError({
          message: `Unable to render sailzenCite for dest ${dest}`,
        });
    }
  };

  return {
    handlers: {
      [DendronASTTypes.SAILZEN_CITE]: handleSailzenCite,
    } as any,
  };
}

type PluginOpts = {};

const plugin: Plugin<[PluginOpts?]> = function (
  this: Processor,
  _opts?: PluginOpts
) {
  const proc = this;
  const data = proc.data();

  // Add micromark syntax extension
  const micromarkExtensions =
    (data.micromarkExtensions as MicromarkExtension[]) || [];
  micromarkExtensions.push(createSailzenCiteSyntax());
  data.micromarkExtensions = micromarkExtensions;

  // Add fromMarkdown extension
  const fromMarkdownExtensions =
    (data.fromMarkdownExtensions as FromMarkdownExtension[]) || [];
  fromMarkdownExtensions.push(createFromMarkdownExtension());
  data.fromMarkdownExtensions = fromMarkdownExtensions;

  // Add toMarkdown extension (for stringification)
  const toMarkdownExtensions =
    (data.toMarkdownExtensions as ToMarkdownExtension[]) || [];
  toMarkdownExtensions.push(createToMarkdownExtension(proc));
  data.toMarkdownExtensions = toMarkdownExtensions;
};

export { plugin as sailzenCite };
