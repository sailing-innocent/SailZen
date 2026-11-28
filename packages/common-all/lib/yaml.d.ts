import { Result } from "neverthrow";
import type { AnyJson } from "./types";
import { SailError } from "./error";
export declare const fromStr: (str: string, overwriteDuplicate?: boolean) => Result<AnyJson, SailError>;
export declare const toStr: (data: any) => Result<string, SailError<import("http-status-codes").StatusCodes | undefined>>;
