import { Logger, createLogger, createDisposableLogger, logAndThrow } from "../logger.js";

describe("Logger", () => {
  describe("Logger class", () => {
    it("should create a logger with name and level", () => {
      const logger = new Logger({ name: "test-logger", level: "info" });
      expect(logger.name).toBe("test-logger");
      expect(logger.level).toBe("info");
    });

    it("should have debug, info, and error methods", () => {
      const logger = new Logger({ name: "test", level: "debug" });
      expect(typeof logger.debug).toBe("function");
      expect(typeof logger.info).toBe("function");
      expect(typeof logger.error).toBe("function");
    });

    it("should log messages", () => {
      const logger = new Logger({ name: "test", level: "info" });
      // Test that the method exists and can be called without error
      expect(() => {
        logger.info({ msg: "test message" });
      }).not.toThrow();
    });

    it("should include context in log messages", () => {
      const logger = new Logger({ name: "test", level: "info" });
      // Test that the method can handle context without error
      expect(() => {
        logger.info({ msg: "test", ctx: "test-context" });
      }).not.toThrow();
    });
  });

  describe("createLogger", () => {
    it("should create a pino logger", () => {
      const logger = createLogger("test-logger");
      expect(logger).toBeDefined();
      expect(typeof logger.info).toBe("function");
      expect(typeof logger.debug).toBe("function");
      expect(typeof logger.error).toBe("function");
    });

    it("should create logger with custom level", () => {
      const logger = createLogger("test-logger", undefined, { lvl: "debug" });
      expect(logger).toBeDefined();
    });
  });

  describe("createDisposableLogger", () => {
    it("should create a disposable logger", () => {
      const result = createDisposableLogger("test-logger");
      expect(result.logger).toBeDefined();
      expect(typeof result.dispose).toBe("function");
    });

    it("should dispose logger without error", () => {
      const result = createDisposableLogger("test-logger");
      expect(() => result.dispose()).not.toThrow();
    });

    it("should create logger with custom level", () => {
      const result = createDisposableLogger("test-logger", undefined, { lvl: "error" });
      expect(result.logger).toBeDefined();
      expect(typeof result.dispose).toBe("function");
    });
  });

  describe("logAndThrow", () => {
    it("should log error and throw", () => {
      const logger = new Logger({ name: "test", level: "error" });
      
      expect(() => {
        logAndThrow(logger, { msg: "test error" });
      }).toThrow();
    });

    it("should throw stringified error message", () => {
      const logger = new Logger({ name: "test", level: "error" });
      
      expect(() => {
        logAndThrow(logger, { msg: "test error" });
      }).toThrow(JSON.stringify({ msg: "test error" }));
    });
  });
});
