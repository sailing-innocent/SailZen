import fs from "fs-extra";
import os from "os";
import path from "path";
import { tmpdir } from "os";
import {
  cleanFileName,
  resolveTilde,
  resolvePath,
  removeMDExtension,
  readYAML,
  writeYAML,
  readYAMLAsync,
  writeYAMLAsync,
  deleteFile,
  readString,
  readJson,
} from "../files.js";

describe("files", () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(tmpdir(), "test-"));
  });

  afterEach(() => {
    if (fs.existsSync(tempDir)) {
      fs.removeSync(tempDir);
    }
  });

  describe("cleanFileName", () => {
    it("should clean file name by removing extension and replacing dots with dashes", () => {
      const result = cleanFileName("test.file.md");
      expect(result).toBe("test-file");
    });

    it("should handle file names with multiple dots", () => {
      const result = cleanFileName("test.file.name.md");
      expect(result).toBe("test-file-name");
    });

    it("should handle directory names when isDir is true", () => {
      const result = cleanFileName("test.dir.name", { isDir: true });
      expect(result).toContain("test-dir-name");
    });

    it("should handle file names with spaces", () => {
      const result = cleanFileName("test file.md");
      expect(result).toBe("test-file");
    });

    it("should handle file names with special characters", () => {
      const result = cleanFileName("test_file.md");
      expect(result).toBe("test_file");
    });

    it("should handle file names without extension", () => {
      const result = cleanFileName("testfile");
      expect(result).toBe("testfile");
    });
  });

  describe("resolveTilde", () => {
    it("should resolve ~ to home directory", () => {
      const result = resolveTilde("~");
      expect(result).toBe(os.homedir());
    });

    it("should resolve ~/path to home directory path", () => {
      // On Windows, ~/path uses forward slash, but path.sep is backslash
      // So we need to use the platform-specific separator
      const testPath = `~${path.sep}test${path.sep}path`;
      const result = resolveTilde(testPath);
      expect(result).toBe(path.join(os.homedir(), "test", "path"));
    });

    it("should return empty string for empty input", () => {
      const result = resolveTilde("");
      expect(result).toBe("");
    });

    it("should return empty string for non-string input", () => {
      const result = resolveTilde(null as any);
      expect(result).toBe("");
    });

    it("should not modify paths without tilde", () => {
      const result = resolveTilde("/some/path");
      expect(result).toBe("/some/path");
    });
  });

  describe("resolvePath", () => {
    it("should resolve absolute paths", () => {
      const absolutePath = path.resolve("/absolute/path");
      const result = resolvePath(absolutePath);
      expect(result).toBe(absolutePath);
    });

    it("should resolve relative paths with root", () => {
      const root = "/workspace";
      const result = resolvePath("relative/path", root);
      expect(result).toBe(path.join(root, "relative", "path"));
    });

    it("should throw error for relative path without root", () => {
      expect(() => {
        resolvePath("relative/path");
      }).toThrow("can't use rel path without a workspace root set");
    });

    it("should resolve tilde paths", () => {
      // Use platform-specific separator
      const testPath = `~${path.sep}test`;
      const result = resolvePath(testPath);
      expect(result).toBe(path.join(os.homedir(), "test"));
    });

    it("should handle Windows paths", () => {
      const isWin = os.platform() === "win32";
      if (isWin) {
        const result = resolvePath("\\windows\\path");
        expect(result).toBe("\\windows\\path");
      } else {
        // On non-Windows, backslash paths are treated as relative
        expect(() => {
          resolvePath("\\windows\\path");
        }).toThrow();
      }
    });
  });

  describe("removeMDExtension", () => {
    it("should remove .md extension from file path", () => {
      const result = removeMDExtension("test.md");
      expect(result).toBe("test");
    });

    it("should remove .md extension from path with directory", () => {
      const result = removeMDExtension("path/to/file.md");
      expect(result).toBe("path/to/file");
    });

    it("should handle paths without .md extension", () => {
      const result = removeMDExtension("test.txt");
      expect(result).toBe("test.txt");
    });

    it("should handle paths ending with .md but not extension", () => {
      // removeMDExtension uses lastIndexOf(".md"), so it will remove .md from anywhere
      const result = removeMDExtension("test.md.other");
      expect(result).toBe("test"); // lastIndexOf finds .md at index 4, slices to there
    });

    it("should handle empty string", () => {
      const result = removeMDExtension("");
      expect(result).toBe("");
    });
  });

  describe("readYAML and writeYAML", () => {
    it("should write and read YAML file", () => {
      const testFile = path.join(tempDir, "test.yaml");
      const testData = { name: "test", value: 123, nested: { key: "value" } };

      writeYAML(testFile, testData);
      expect(fs.existsSync(testFile)).toBe(true);

      const result = readYAML(testFile);
      expect(result).toEqual(testData);
    });

    it("should handle YAML with arrays", () => {
      const testFile = path.join(tempDir, "test.yaml");
      const testData = { items: ["a", "b", "c"] };

      writeYAML(testFile, testData);
      const result = readYAML(testFile);
      expect(result).toEqual(testData);
    });

    it("should handle empty YAML object", () => {
      const testFile = path.join(tempDir, "test.yaml");
      const testData = {};

      writeYAML(testFile, testData);
      const result = readYAML(testFile);
      expect(result).toEqual(testData);
    });
  });

  describe("readYAMLAsync and writeYAMLAsync", () => {
    it("should write and read YAML file asynchronously", async () => {
      const testFile = path.join(tempDir, "test-async.yaml");
      const testData = { name: "test", value: 456 };

      await writeYAMLAsync(testFile, testData);
      expect(await fs.pathExists(testFile)).toBe(true);

      const result = await readYAMLAsync(testFile);
      expect(result).toEqual(testData);
    });

    it("should handle complex nested structures", async () => {
      const testFile = path.join(tempDir, "test-nested.yaml");
      const testData = {
        level1: {
          level2: {
            level3: "deep",
          },
        },
      };

      await writeYAMLAsync(testFile, testData);
      const result = await readYAMLAsync(testFile);
      expect(result).toEqual(testData);
    });
  });

  describe("deleteFile", () => {
    it("should delete existing file", () => {
      const testFile = path.join(tempDir, "test.txt");
      fs.writeFileSync(testFile, "test content");

      expect(fs.existsSync(testFile)).toBe(true);
      deleteFile(testFile);
      expect(fs.existsSync(testFile)).toBe(false);
    });

    it("should throw error when deleting non-existent file", () => {
      const testFile = path.join(tempDir, "non-existent.txt");
      expect(() => {
        deleteFile(testFile);
      }).toThrow();
    });
  });

  describe("readString", () => {
    it("should read file content as string", () => {
      const testFile = path.join(tempDir, "test.txt");
      const content = "test content\nwith newlines";
      fs.writeFileSync(testFile, content, "utf8");

      const result = readString(testFile);
      expect(result.isOk()).toBe(true);
      if (result.isOk()) {
        expect(result.value).toBe(content);
      }
    });

    it("should return error for non-existent file", () => {
      const testFile = path.join(tempDir, "non-existent.txt");
      const result = readString(testFile);
      expect(result.isErr()).toBe(true);
    });
  });

  describe("readJson", () => {
    it("should read JSON file", async () => {
      const testFile = path.join(tempDir, "test.json");
      const testData = { name: "test", value: 789 };
      fs.writeFileSync(testFile, JSON.stringify(testData), "utf8");

      const result = await readJson(testFile);
      expect(result.isOk()).toBe(true);
      if (result.isOk()) {
        expect(result.value).toEqual(testData);
      }
    });

    it("should return error for invalid JSON file", async () => {
      const testFile = path.join(tempDir, "invalid.json");
      fs.writeFileSync(testFile, "invalid json content", "utf8");

      const result = await readJson(testFile);
      expect(result.isErr()).toBe(true);
    });

    it("should return error for non-existent file", async () => {
      const testFile = path.join(tempDir, "non-existent.json");
      const result = await readJson(testFile);
      expect(result.isErr()).toBe(true);
    });
  });
});
