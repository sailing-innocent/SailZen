import { getOS, getDurationMilliseconds } from "./system.js";
import process from "process";

describe("system", () => {
  describe("getOS", () => {
    it("should return the operating system platform", () => {
      const os = getOS();
      expect(os).toBeDefined();
      expect(typeof os).toBe("string");
      // Common platforms: 'win32', 'darwin', 'linux'
      expect(["win32", "darwin", "linux", "freebsd", "openbsd"]).toContain(os);
    });

    it("should return consistent results", () => {
      const os1 = getOS();
      const os2 = getOS();
      expect(os1).toBe(os2);
    });
  });

  describe("getDurationMilliseconds", () => {
    it("should calculate duration correctly", () => {
      const start: [number, number] = [0, 0];
      const end: [number, number] = [1, 500000000]; // 1 second + 500ms in nanoseconds
      
      // Mock hrtime to return predictable values
      const originalHrtime = process.hrtime;
      const mockHrtime = () => end;
      (mockHrtime as any).bigint = () => BigInt(1500000000);
      process.hrtime = mockHrtime as unknown as typeof process.hrtime;
      
      const duration = getDurationMilliseconds(start);
      
      // 1 second = 1000ms, 500000000 nanoseconds = 500ms
      expect(duration).toBe(1500);
      
      process.hrtime = originalHrtime;
    });

    it("should handle zero duration", () => {
      const start: [number, number] = [0, 0];
      const end: [number, number] = [0, 0];
      
      const originalHrtime = process.hrtime;
      const mockHrtime = () => end;
      (mockHrtime as any).bigint = () => BigInt(0);
      process.hrtime = mockHrtime as unknown as typeof process.hrtime;
      
      const duration = getDurationMilliseconds(start);
      expect(duration).toBe(0);
      
      process.hrtime = originalHrtime;
    });

    it("should handle sub-millisecond durations", () => {
      const start: [number, number] = [0, 0];
      const end: [number, number] = [0, 500000]; // 0.5ms in nanoseconds
      
      const originalHrtime = process.hrtime;
      const mockHrtime = () => end;
      (mockHrtime as any).bigint = () => BigInt(500000);
      process.hrtime = mockHrtime as unknown as typeof process.hrtime;
      
      const duration = getDurationMilliseconds(start);
      // Should round down to 0ms for sub-millisecond durations
      expect(duration).toBe(0);
      
      process.hrtime = originalHrtime;
    });

    it("should handle real timing", (done) => {
      const start = process.hrtime();
      
      setTimeout(() => {
        const duration = getDurationMilliseconds(start);
        expect(duration).toBeGreaterThanOrEqual(90); // At least 90ms
        expect(duration).toBeLessThan(150); // Less than 150ms
        done();
      }, 100);
    });
  });
});
