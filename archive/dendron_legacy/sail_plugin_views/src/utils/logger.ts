import { Amplify, ConsoleLogger } from "@aws-amplify/core";

export enum LOG_LEVEL {
  DEBUG = "DEBUG",
  INFO = "INFO",
  ERROR = "ERROR",
}

export function createLogger(name: string) {
  return new ConsoleLogger(name);
}

export function setLogLevel(lvl: LOG_LEVEL) {
  // Note: Amplify v6 may have different API for log level
  // This may need adjustment based on actual Amplify v6 API
  if ((Amplify as any).Logger) {
    (Amplify as any).Logger.LOG_LEVEL = lvl;
  }
}
