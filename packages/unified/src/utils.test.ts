import {
  MDUtilsV5,
  ProcFlavor
} from "./utilsv5";

import { NoteProps, DVault, DendronConfig, genDefaultDendronConfig, NoteUtils } from "@saili/common-all";

describe('Simple Use for Unified', () => {
    test("should 1 == 1 utils", async () => {
        const dvault: DVault = {
            fsPath: "/test/dvault",
        }
        let md = "[[World|src://world]] $\\frac{1}{2}$"
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
            type: "note", // Replace with appropriate DNodeType if needed
            parent: "",
            children: [],
            stub: false,
            custom: {},
            tags: [],
            traits: [],
            vault: dvault,
            data: {}, // Add appropriate mock data if needed
            body: md  // Add appropriate mock body if needed
        }
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
        // expect(renderedNote).toContain("Test Note");
        console.log("Rendered Note:", renderedNote);
        expect(renderedNote).toBeDefined();
    });
});