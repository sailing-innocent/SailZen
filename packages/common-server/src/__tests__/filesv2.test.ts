import fs from "fs-extra";
import path from "path";
import { tmpdir } from "os";
import {
  dot2Slash,
  isInsidePath,
  uniqueOutermostFolders,
  tmpDir,
  fileExists,
} from "../filesv2.js";

describe("filesv2", () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(tmpdir(), "test-"));
  });

  afterEach(() => {
    if (fs.existsSync(tempDir)) {
      fs.removeSync(tempDir);
    }
  });

  describe("dot2Slash", () => {
    it("should convert dot-separated filename to slash-separated", () => {
      const result = dot2Slash("test.file.name");
      expect(result).toBe("test/file/name");
    });

    it("should handle single dot", () => {
      const result = dot2Slash("test.file");
      expect(result).toBe("test/file");
    });

    it("should handle multiple consecutive dots", () => {
      const result = dot2Slash("test..file");
      expect(result).toBe("test//file");
    });

    it("should handle filename without dots", () => {
      const result = dot2Slash("testfile");
      expect(result).toBe("testfile");
    });

    it("should handle empty string", () => {
      const result = dot2Slash("");
      expect(result).toBe("");
    });

    it("should handle path with slashes and dots", () => {
      const result = dot2Slash("path/to/test.file.name");
      expect(result).toBe("path/to/test/file/name");
    });
  });

  describe("isInsidePath", () => {
    it("should return true when inner path is inside outer path", () => {
      const outer = "/workspace/project";
      const inner = "/workspace/project/subfolder/file.txt";
      expect(isInsidePath(outer, inner)).toBe(true);
    });

    it("should return false when inner path is outside outer path", () => {
      const outer = "/workspace/project";
      const inner = "/workspace/other/file.txt";
      expect(isInsidePath(outer, inner)).toBe(false);
    });

    it("should return false when paths are equal", () => {
      // According to the function documentation, equal paths return false
      const testPath = "/workspace/project";
      expect(isInsidePath(testPath, testPath)).toBe(false);
    });

    it("should handle relative paths", () => {
      const outer = "workspace/project";
      const inner = "workspace/project/subfolder";
      expect(isInsidePath(outer, inner)).toBe(true);
    });

    it("should handle Windows-style paths", () => {
      const outer = "C:\\workspace\\project";
      const inner = "C:\\workspace\\project\\subfolder";
      expect(isInsidePath(outer, inner)).toBe(true);
    });

    it("should return false for paths that share prefix but are not nested", () => {
      const outer = "/workspace/project";
      const inner = "/workspace/project2/file.txt";
      expect(isInsidePath(outer, inner)).toBe(false);
    });
  });

  describe("uniqueOutermostFolders", () => {
    it("should return unique outermost folders", () => {
      const folders = [
        "/workspace/project",
        "/workspace/project/subfolder",
        "/workspace/other",
      ];
      const result = uniqueOutermostFolders(folders);
      expect(result).toHaveLength(2);
      expect(result).toContain("/workspace/project");
      expect(result).toContain("/workspace/other");
    });

    it("should remove nested folders", () => {
      const folders = [
        "/workspace/project",
        "/workspace/project/subfolder",
        "/workspace/project/subfolder/deep",
        "/workspace/other",
      ];
      const result = uniqueOutermostFolders(folders);
      expect(result).toHaveLength(2);
      expect(result).toContain("/workspace/project");
      expect(result).toContain("/workspace/other");
    });

    it("should handle empty array", () => {
      const result = uniqueOutermostFolders([]);
      expect(result).toEqual([]);
    });

    it("should handle single folder", () => {
      const folders = ["/workspace/project"];
      const result = uniqueOutermostFolders(folders);
      expect(result).toEqual(folders);
    });

    it("should handle folders at same level", () => {
      const folders = [
        "/workspace/project1",
        "/workspace/project2",
        "/workspace/project3",
      ];
      const result = uniqueOutermostFolders(folders);
      expect(result).toHaveLength(3);
    });

    it("should handle Windows paths", () => {
      const folders = [
        "C:\\workspace\\project",
        "C:\\workspace\\project\\subfolder",
        "C:\\workspace\\other",
      ];
      const result = uniqueOutermostFolders(folders);
      expect(result).toHaveLength(2);
    });
  });

  describe("tmpDir", () => {
    it("should create a temporary directory", () => {
      const result = tmpDir();
      expect(result).toBeDefined();
      expect(result.name).toBeDefined();
      expect(typeof result.name).toBe("string");
      expect(fs.existsSync(result.name)).toBe(true);
      expect(fs.statSync(result.name).isDirectory()).toBe(true);
    });

    it("should create different directories on each call", () => {
      const dir1 = tmpDir();
      const dir2 = tmpDir();
      expect(dir1.name).not.toBe(dir2.name);
    });

    it("should have removeCallback function", () => {
      const result = tmpDir();
      expect(typeof result.removeCallback).toBe("function");
    });

    it("should allow cleanup via removeCallback", () => {
      const result = tmpDir();
      const dirPath = result.name;
      expect(fs.existsSync(dirPath)).toBe(true);

      result.removeCallback();
      expect(fs.existsSync(dirPath)).toBe(false);
    });
  });

  describe("fileExists", () => {
    it("should return true for existing file", async () => {
      const testFile = path.join(tempDir, "test.txt");
      fs.writeFileSync(testFile, "test content");

      const result = await fileExists(testFile);
      expect(result).toBe(true);
    });

    it("should return false for non-existent file", async () => {
      const testFile = path.join(tempDir, "non-existent.txt");
      const result = await fileExists(testFile);
      expect(result).toBe(false);
    });

    it("should return false for directory", async () => {
      const testDir = path.join(tempDir, "test-dir");
      fs.mkdirSync(testDir);

      const result = await fileExists(testDir);
      expect(result).toBe(false);
    });

    it("should handle paths with special characters", async () => {
      const testFile = path.join(tempDir, "test-file.txt");
      fs.writeFileSync(testFile, "content");

      const result = await fileExists(testFile);
      expect(result).toBe(true);
    });
  });
});
