import type {
  ISailError,
  NonOptional,
  NoteProps,
  Decoration,
  SailConfig,
  ReducedDEngine,
} from "@saili/common-all";
import { Node } from "hast";
import { SailASTNode } from "../types";

export { DECORATION_TYPES } from "@saili/common-all";
export type { Decoration };

export type DecoratorOut<D extends Decoration = Decoration> = {
  decorations: D[];
  errors?: ISailError[];
};

export type DecoratorIn<N extends Omit<SailASTNode, "children"> = SailASTNode> = {
  node: NonOptional<N, "position">;
  note: NoteProps;
  noteText: string;
  engine: ReducedDEngine;
  config: SailConfig;
};

export type Decorator<
  N extends Omit<SailASTNode, "children">,
  D extends Decoration = Decoration
> = (opts: DecoratorIn<N>) => DecoratorOut<D> | Promise<DecoratorOut<D>>;
