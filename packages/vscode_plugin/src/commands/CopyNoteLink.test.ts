/**
 * @file CopyNoteLink.test.ts
 * @brief Test cases for CopyNoteLink command
 * @description Tests for the issue where findNotesMeta returns empty array or incomplete note objects
 */

import { CopyNoteLinkCommand } from "./CopyNoteLink";
import { IDendronExtension } from "../dendronExtensionInterface";
import { NotePropsMeta, DVault } from "@saili/common-all";
import { TextEditor, TextDocument, Uri, Selection, Position } from "vscode";
import { DEngineClient } from "@saili/common-all";

// Mock modules
jest.mock("../vsCodeUtils");
jest.mock("../components/lookup/utils");
jest.mock("../utils/EditorUtils");
jest.mock("../clientUtils");
jest.mock("../utils");
jest.mock("vscode");

describe("CopyNoteLinkCommand", () => {
  let mockExtension: IDendronExtension;
  let mockEngine: DEngineClient;
  let mockEditor: TextEditor;
  let mockDocument: TextDocument;
  let command: CopyNoteLinkCommand;
  let mockVault: DVault;

  beforeEach(() => {
    jest.clearAllMocks();
    // Setup mock vault
    mockVault = {
      fsPath: "/test/vault",
      name: "test-vault",
    };

    // Setup mock document
    mockDocument = {
      uri: Uri.file("/test/vault/test-note.md"),
      isDirty: false,
      lineAt: jest.fn((line: number) => ({
        text: "Test line",
        range: {
          start: new Position(line, 0),
          end: new Position(line, 10),
        },
      })),
    } as unknown as TextDocument;

    // Setup mock editor
    mockEditor = {
      document: mockDocument,
      selection: new Selection(0, 0, 0, 0),
      edit: jest.fn(),
    } as unknown as TextEditor;

    // Setup mock engine
    mockEngine = {
      findNotesMeta: jest.fn(),
      wsRoot: "/test",
      vaults: [mockVault],
    } as unknown as DEngineClient;

    // Setup mock extension
    mockExtension = {
      getEngine: jest.fn(() => mockEngine),
      getDWorkspace: jest.fn(() => ({
        wsRoot: "/test",
        vaults: [mockVault],
        config: {},
      })),
    } as unknown as IDendronExtension;

    command = new CopyNoteLinkCommand(mockExtension);
  });

  describe("findNotesMeta returns empty array", () => {
    it("should handle empty array from findNotesMeta gracefully", async () => {
      // Mock findNotesMeta to return empty array
      (mockEngine.findNotesMeta as jest.Mock).mockResolvedValue([]);

      // Mock VSCodeUtils
      const { VSCodeUtils } = await import("../vsCodeUtils");
      (VSCodeUtils.getActiveTextEditor as jest.Mock).mockReturnValue(mockEditor);
      (VSCodeUtils.getSelection as jest.Mock).mockReturnValue({
        start: new Position(0, 0),
        end: new Position(0, 0),
      });

      // Mock PickerUtilsV2
      const { PickerUtilsV2 } = await import("../components/lookup/utils");
      (PickerUtilsV2.getVaultForOpenEditor as jest.Mock).mockReturnValue(
        mockVault
      );

      // Mock EditorUtils
      const { EditorUtils } = await import("../utils/EditorUtils");
      (EditorUtils.getSelectionAnchors as jest.Mock).mockResolvedValue({
        startAnchor: undefined,
      });

      // Mock clipboard
      const { clipboard } = await import("../utils");
      (clipboard.writeText as jest.Mock).mockImplementation(() => {});

      // Mock window.showInformationMessage
      const { window } = await import("vscode");
      (window.showInformationMessage as jest.Mock).mockResolvedValue(
        undefined
      );

      // Execute command
      const result = await command.execute({});

      // Verify that findNotesMeta was called
      expect(mockEngine.findNotesMeta).toHaveBeenCalledWith({
        fname: "test-note",
        vault: mockVault,
      });

      // Verify that executeCopyNoteLink was called with undefined note
      // (should fall back to non-note file link)
      expect(result).toBeDefined();
      expect(result?.type).toBe("non-note");
    });
  });

  describe("findNotesMeta returns incomplete note object", () => {
    it("should handle note without id property", async () => {
      // Mock findNotesMeta to return note without id
      const incompleteNote: Partial<NotePropsMeta> = {
        fname: "test-note",
        vault: mockVault,
        title: "Test Note",
        // Missing id property
      };
      (mockEngine.findNotesMeta as jest.Mock).mockResolvedValue([
        incompleteNote as NotePropsMeta,
      ]);

      // Mock VSCodeUtils
      const { VSCodeUtils } = await import("../vsCodeUtils");
      (VSCodeUtils.getActiveTextEditor as jest.Mock).mockReturnValue(mockEditor);
      (VSCodeUtils.getSelection as jest.Mock).mockReturnValue({
        start: new Position(0, 0),
        end: new Position(0, 0),
      });

      // Mock PickerUtilsV2
      const { PickerUtilsV2 } = await import("../components/lookup/utils");
      (PickerUtilsV2.getVaultForOpenEditor as jest.Mock).mockReturnValue(
        mockVault
      );

      // Mock EditorUtils
      const { EditorUtils } = await import("../utils/EditorUtils");
      (EditorUtils.getSelectionAnchors as jest.Mock).mockResolvedValue({
        startAnchor: undefined,
      });

      // Mock clipboard
      const { clipboard } = await import("../utils");
      (clipboard.writeText as jest.Mock).mockImplementation(() => {});

      // Mock window.showInformationMessage
      const { window } = await import("vscode");
      (window.showInformationMessage as jest.Mock).mockResolvedValue(
        undefined
      );

      // Execute command
      const result = await command.execute({});

      // Verify that findNotesMeta was called
      expect(mockEngine.findNotesMeta).toHaveBeenCalledWith({
        fname: "test-note",
        vault: mockVault,
      });

      // Verify that it falls back to non-note file link when note is incomplete
      expect(result).toBeDefined();
      expect(result?.type).toBe("non-note");
    });

    it("should handle note without fname property", async () => {
      // Mock findNotesMeta to return note without fname
      const incompleteNote: Partial<NotePropsMeta> = {
        id: "test-id",
        vault: mockVault,
        title: "Test Note",
        // Missing fname property
      };
      (mockEngine.findNotesMeta as jest.Mock).mockResolvedValue([
        incompleteNote as NotePropsMeta,
      ]);

      // Mock VSCodeUtils
      const { VSCodeUtils } = await import("../vsCodeUtils");
      (VSCodeUtils.getActiveTextEditor as jest.Mock).mockReturnValue(mockEditor);
      (VSCodeUtils.getSelection as jest.Mock).mockReturnValue({
        start: new Position(0, 0),
        end: new Position(0, 0),
      });

      // Mock PickerUtilsV2
      const { PickerUtilsV2 } = await import("../components/lookup/utils");
      (PickerUtilsV2.getVaultForOpenEditor as jest.Mock).mockReturnValue(
        mockVault
      );

      // Mock EditorUtils
      const { EditorUtils } = await import("../utils/EditorUtils");
      (EditorUtils.getSelectionAnchors as jest.Mock).mockResolvedValue({
        startAnchor: undefined,
      });

      // Mock clipboard
      const { clipboard } = await import("../utils");
      (clipboard.writeText as jest.Mock).mockImplementation(() => {});

      // Mock window.showInformationMessage
      const { window } = await import("vscode");
      (window.showInformationMessage as jest.Mock).mockResolvedValue(
        undefined
      );

      // Execute command
      const result = await command.execute({});

      // Verify that it falls back to non-note file link when note is incomplete
      expect(result).toBeDefined();
      expect(result?.type).toBe("non-note");
    });

    it("should handle note without vault property", async () => {
      // Mock findNotesMeta to return note without vault
      const incompleteNote: Partial<NotePropsMeta> = {
        id: "test-id",
        fname: "test-note",
        title: "Test Note",
        // Missing vault property
      };
      (mockEngine.findNotesMeta as jest.Mock).mockResolvedValue([
        incompleteNote as NotePropsMeta,
      ]);

      // Mock VSCodeUtils
      const { VSCodeUtils } = await import("../vsCodeUtils");
      (VSCodeUtils.getActiveTextEditor as jest.Mock).mockReturnValue(mockEditor);
      (VSCodeUtils.getSelection as jest.Mock).mockReturnValue({
        start: new Position(0, 0),
        end: new Position(0, 0),
      });

      // Mock PickerUtilsV2
      const { PickerUtilsV2 } = await import("../components/lookup/utils");
      (PickerUtilsV2.getVaultForOpenEditor as jest.Mock).mockReturnValue(
        mockVault
      );

      // Mock EditorUtils
      const { EditorUtils } = await import("../utils/EditorUtils");
      (EditorUtils.getSelectionAnchors as jest.Mock).mockResolvedValue({
        startAnchor: undefined,
      });

      // Mock clipboard
      const { clipboard } = await import("../utils");
      (clipboard.writeText as jest.Mock).mockImplementation(() => {});

      // Mock window.showInformationMessage
      const { window } = await import("vscode");
      (window.showInformationMessage as jest.Mock).mockResolvedValue(
        undefined
      );

      // Execute command
      const result = await command.execute({});

      // Verify that it falls back to non-note file link when note is incomplete
      expect(result).toBeDefined();
      expect(result?.type).toBe("non-note");
    });
  });

  describe("findNotesMeta returns valid note", () => {
    it("should handle valid note object correctly", async () => {
      // Mock findNotesMeta to return valid note
      const validNote: NotePropsMeta = {
        id: "test-id",
        fname: "test-note",
        vault: mockVault,
        title: "Test Note",
        desc: "Test Description",
        updated: Date.now(),
        created: Date.now(),
        type: "note",
        parent: null,
        children: [],
        links: [],
        anchors: {},
        data: {},
      } as NotePropsMeta;

      (mockEngine.findNotesMeta as jest.Mock).mockResolvedValue([validNote]);

      // Mock VSCodeUtils
      const { VSCodeUtils } = await import("../vsCodeUtils");
      (VSCodeUtils.getActiveTextEditor as jest.Mock).mockReturnValue(mockEditor);
      (VSCodeUtils.getSelection as jest.Mock).mockReturnValue({
        start: new Position(0, 0),
        end: new Position(0, 0),
      });

      // Mock PickerUtilsV2
      const { PickerUtilsV2 } = await import("../components/lookup/utils");
      (PickerUtilsV2.getVaultForOpenEditor as jest.Mock).mockReturnValue(
        mockVault
      );

      // Mock EditorUtils
      const { EditorUtils } = await import("../utils/EditorUtils");
      (EditorUtils.getSelectionAnchors as jest.Mock).mockResolvedValue({
        startAnchor: undefined,
      });

      // Mock DConfig
      const { DConfig } = await import("@saili/common-server");
      (DConfig.readConfigSync as jest.Mock).mockReturnValue({
        useVaultPrefix: false,
      } as any);

      // Mock ConfigUtils
      const { ConfigUtils } = await import("@saili/common-all");
      (ConfigUtils.getAliasMode as jest.Mock).mockReturnValue("title");

      // Mock DendronClientUtilsV2
      const { DendronClientUtilsV2 } = await import("../clientUtils");
      (
        DendronClientUtilsV2.shouldUseVaultPrefix as jest.Mock
      ).mockReturnValue(false);

      // Mock clipboard
      const { clipboard } = await import("../utils");
      (clipboard.writeText as jest.Mock).mockImplementation(() => {});

      // Mock window.showInformationMessage
      const { window } = await import("vscode");
      (window.showInformationMessage as jest.Mock).mockResolvedValue(
        undefined
      );

      // Execute command
      const result = await command.execute({});

      // Verify that findNotesMeta was called
      expect(mockEngine.findNotesMeta).toHaveBeenCalledWith({
        fname: "test-note",
        vault: mockVault,
      });

      // Verify that it creates a note link for valid note
      expect(result).toBeDefined();
      expect(result?.type).toBe("note");
    });
  });
});


