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
import { DendronASTDest, DendronASTTypes, SailZenFigure } from "../types";
import { MDUtilsV5 } from "..";

/**
 * Remark plugin for SailZen ::figure[caption](src){opts} directive.
 *
 * Parses inline figures like:
 *   ::figure[Overview](fig_overview){width=0.8\textwidth}
 *   ::figure[Caption](image.png)
 *
 * And produces a sailzenFigure AST node.
 */

export const FIGURE_REGEX =
  /^::figure\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{([^}]*)\})?/;

// Character codes
const codes = {
  colon: 58,
  f: 102,
  i: 105,
  g: 103,
  u: 117,
  r: 114,
  e: 101,
  openBracket: 91,
  closeBracket: 93,
  openParen: 40,
  closeParen: 41,
  openBrace: 123,
  closeBrace: 125,
};

/**
 * Simple key="value" or key=value parser
 */
function parseOptions(raw: string): Record<string, any> {
  const options: Record<string, any> = {};
  if (!raw) return options;
  const regex = /\s*([^\s=]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s,}]*))/g;
  let match;
  while ((match = regex.exec(raw)) !== null) {
    const key = match[1].trim();
    const value = match[2] || match[3] || match[4];
    if (key) {
      options[key] = value;
    }
  }
  return options;
}

/**
 * Micromark syntax extension for ::figure[caption](src){opts}
 */
function createSailzenFigureSyntax(): MicromarkExtension {
  const tokenizeSailzenFigure: Tokenizer = function (
    effects: Effects,
    ok: State,
    nok: State
  ) {
    return start;

    function start(code: Code): State | undefined {
      if (code !== codes.colon) return nok(code);
      effects.enter("sailzenFigure" as any);
      effects.enter("sailzenFigureMarker" as any);
      effects.consume(code);
      return secondColon;
    }

    function secondColon(code: Code): State | undefined {
      if (code !== codes.colon) return nok(code);
      effects.consume(code);
      effects.exit("sailzenFigureMarker" as any);
      effects.enter("sailzenFigureKeyword" as any);
      return keywordF;
    }

    function keywordF(code: Code): State | undefined {
      if (code !== codes.f) return nok(code);
      effects.consume(code);
      return keywordI;
    }

    function keywordI(code: Code): State | undefined {
      if (code !== codes.i) return nok(code);
      effects.consume(code);
      return keywordG;
    }

    function keywordG(code: Code): State | undefined {
      if (code !== codes.g) return nok(code);
      effects.consume(code);
      return keywordU;
    }

    function keywordU(code: Code): State | undefined {
      if (code !== codes.u) return nok(code);
      effects.consume(code);
      return keywordR;
    }

    function keywordR(code: Code): State | undefined {
      if (code !== codes.r) return nok(code);
      effects.consume(code);
      return keywordE;
    }

    function keywordE(code: Code): State | undefined {
      if (code !== codes.e) return nok(code);
      effects.consume(code);
      effects.exit("sailzenFigureKeyword" as any);
      return openBracket;
    }

    function openBracket(code: Code): State | undefined {
      if (code !== codes.openBracket) return nok(code);
      effects.consume(code);
      effects.enter("sailzenFigureCaption" as any);
      return insideCaption;
    }

    function insideCaption(code: Code): State | undefined {
      if (code === null) return nok(code);
      if (code === codes.closeBracket) {
        effects.exit("sailzenFigureCaption" as any);
        effects.consume(code);
        return openParen;
      }
      effects.consume(code);
      return insideCaption;
    }

    function openParen(code: Code): State | undefined {
      if (code !== codes.openParen) return nok(code);
      effects.consume(code);
      effects.enter("sailzenFigureSrc" as any);
      return insideSrc;
    }

    function insideSrc(code: Code): State | undefined {
      if (code === null) return nok(code);
      if (code === codes.closeParen) {
        effects.exit("sailzenFigureSrc" as any);
        effects.consume(code);
        return optionalBrace;
      }
      effects.consume(code);
      return insideSrc;
    }

    function optionalBrace(code: Code): State | undefined {
      if (code === codes.openBrace) {
        effects.consume(code);
        effects.enter("sailzenFigureOptions" as any);
        return insideOptions;
      }
      effects.exit("sailzenFigure" as any);
      return ok(code);
    }

    function insideOptions(code: Code): State | undefined {
      if (code === null) return nok(code);
      if (code === codes.closeBrace) {
        effects.exit("sailzenFigureOptions" as any);
        effects.consume(code);
        effects.exit("sailzenFigure" as any);
        return ok(code);
      }
      effects.consume(code);
      return insideOptions;
    }
  };

  return {
    text: {
      [codes.colon]: {
        tokenize: tokenizeSailzenFigure,
      },
    },
  };
}

/**
 * mdast-util-from-markdown extension
 * Converts micromark tokens to mdast nodes
 */
function createFromMarkdownExtension(): FromMarkdownExtension {
  const enterSailzenFigure: Handle = function (token) {
    this.enter(
      {
        type: DendronASTTypes.SAILZEN_FIGURE,
        caption: "",
        src: "",
        options: {},
      } as any,
      token
    );
  };

  const exitSailzenFigureCaption: Handle = function (token) {
    const node = this.stack[this.stack.length - 1] as unknown as SailZenFigure;
    node.caption = this.sliceSerialize(token).trim();
  };

  const exitSailzenFigureSrc: Handle = function (token) {
    const node = this.stack[this.stack.length - 1] as unknown as SailZenFigure;
    node.src = this.sliceSerialize(token).trim();
  };

  const exitSailzenFigureOptions: Handle = function (token) {
    const node = this.stack[this.stack.length - 1] as unknown as SailZenFigure;
    const optsRaw = this.sliceSerialize(token).trim();
    node.options = parseOptions(optsRaw);
  };

  const exitSailzenFigure: Handle = function (token) {
    this.exit(token);
  };

  return {
    enter: {
      sailzenFigure: enterSailzenFigure,
    },
    exit: {
      sailzenFigureCaption: exitSailzenFigureCaption,
      sailzenFigureSrc: exitSailzenFigureSrc,
      sailzenFigureOptions: exitSailzenFigureOptions,
      sailzenFigure: exitSailzenFigure,
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
  const handleSailzenFigure: ToMarkdownHandle = function (
    node,
    _parent,
    _state,
    _info
  ) {
    const figNode = node as unknown as SailZenFigure;
    const dest = getDest(proc);
    const { caption, src, options } = figNode;
    switch (dest) {
      case DendronASTDest.MD_DENDRON:
      case DendronASTDest.MD_REGULAR: {
        const optsStr =
          options && Object.keys(options).length
            ? "{" + Object.entries(options).map(([k, v]) => `${k}="${v}"`).join(", ") + "}"
            : "";
        return `::figure[${caption}](${src})${optsStr}`;
      }
      case DendronASTDest.HTML:
        return `<figure>\n  <img src="${src}" alt="${caption}" />\n  <figcaption>${caption}</figcaption>\n</figure>`;
      case DendronASTDest.DOC_EXPORT:
        return `__FIGURE__[${src}|${caption}]`;
      case DendronASTDest.DOC_PREVIEW:
        return `<figure class="sailzen-figure">\n  <div class="sailzen-figure-placeholder">📷 ${src}</div>\n  <figcaption>${caption}</figcaption>\n</figure>`;
      default:
        throw new DendronError({
          message: `Unable to render sailzenFigure for dest ${dest}`,
        });
    }
  };

  return {
    handlers: {
      [DendronASTTypes.SAILZEN_FIGURE]: handleSailzenFigure,
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
  micromarkExtensions.push(createSailzenFigureSyntax());
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

export { plugin as sailzenFigure };
