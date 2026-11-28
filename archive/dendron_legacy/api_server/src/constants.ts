import { SailError } from "@saili/common-all";

export const LOG_FILE_NAME = "sail.server.log";
export const LOGGER_NAME = "api-server";

export function getLogPath(): string {
  if (!process.env["LOG_DST"]) {
    throw new SailError({ message: "log not set" });
  }
  return process.env["LOG_DST"];
}
