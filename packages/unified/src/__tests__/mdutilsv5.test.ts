/**
 * Tests for MDUtilsV5 processor
 */
import {
  MDUtilsV5,
  ProcFlavor
} from "../utilsv5";

import { NoteProps, DVault, DendronConfig, genDefaultDendronConfig, NoteUtils } from "@saili/common-all";

describe("MDUtilsV5", () => {
  describe("procRehypeFull", () => {
    it("should process markdown with wiki links and math", async () => {
      const dvault: DVault = {
        fsPath: "/test/dvault",
      };
      let md = "[[World|src://world]] $\\frac{1}{2}$";
      md = "# Header \n some content \n\n ## Subheader \n\n" + md;
      const note: NoteProps = {
        id: "test-id",
        fname: "test",
        title: "Test Note",
        desc: "This is a test note",
        created: 234899,
        updated: 248990,
        links: [],
        anchors: {},
        type: "note",
        parent: "",
        children: [],
        stub: false,
        custom: {},
        tags: [],
        traits: [],
        vault: dvault,
        data: {},
        body: md
      };
      const flavor = ProcFlavor.REGULAR;
      const config: DendronConfig = genDefaultDendronConfig();
      const proc = MDUtilsV5.procRehypeFull(
        {
          noteToRender: note,
          fname: note.fname,
          vault: note.vault,
          config,
        },
        { flavor }
      );
      const payload = await proc.process(NoteUtils.serialize(note));
      const renderedNote = payload.toString();
      expect(renderedNote).toBeDefined();
    });

    it("should handle empty body", async () => {
      const dvault: DVault = {
        fsPath: "/test/dvault",
      };
      const note: NoteProps = {
        id: "test-id",
        fname: "test",
        title: "Test Note",
        desc: "",
        created: 234899,
        updated: 248990,
        links: [],
        anchors: {},
        type: "note",
        parent: "",
        children: [],
        stub: false,
        custom: {},
        tags: [],
        traits: [],
        vault: dvault,
        data: {},
        body: ""
      };
      const config: DendronConfig = genDefaultDendronConfig();
      const proc = MDUtilsV5.procRehypeFull(
        {
          noteToRender: note,
          fname: note.fname,
          vault: note.vault,
          config,
        },
        { flavor: ProcFlavor.REGULAR }
      );
      const payload = await proc.process(NoteUtils.serialize(note));
      expect(payload.toString()).toBeDefined();
    });

    it("should render headers correctly", async () => {
      const dvault: DVault = {
        fsPath: "/test/dvault",
      };
      const note: NoteProps = {
        id: "test-id",
        fname: "test",
        title: "Test Note",
        desc: "",
        created: 234899,
        updated: 248990,
        links: [],
        anchors: {},
        type: "note",
        parent: "",
        children: [],
        stub: false,
        custom: {},
        tags: [],
        traits: [],
        vault: dvault,
        data: {},
        body: "# Main Header\n\n## Sub Header\n\n### Third Level"
      };
      const config: DendronConfig = genDefaultDendronConfig();
      const proc = MDUtilsV5.procRehypeFull(
        {
          noteToRender: note,
          fname: note.fname,
          vault: note.vault,
          config,
        },
        { flavor: ProcFlavor.REGULAR }
      );
      const payload = await proc.process(NoteUtils.serialize(note));
      const html = payload.toString();
      expect(html).toContain("<h1");
      expect(html).toContain("<h2");
      expect(html).toContain("<h3");
    });
  });
});
