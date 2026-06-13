---
id: Hf27I1UR3HvKyd6HRh8C0
title: Assets
desc: ''
updated: 1649146018848
created: 1637568178090
---

## PDF pasted with `Sail: Paste File` command
 Should open the following assets with default app when clicking the link within preview:
* [dummy-pdf.pdf](assets/dummy-pdf.pdf) 
* [dummy-pdf.pdf](./assets/dummy-pdf.pdf) 
* [dummy-pdf.pdf](/assets/dummy-pdf.pdf)

* [with space encoded](assets/file%20with%20space.pdf)
* [with space encoded](./assets/file%20with%20space.pdf)
* [with space encoded](/assets/file%20with%20space.pdf)

* [with space wrapped](<assets/file with space.pdf>)
* [with space wrapped](<./assets/file with space.pdf>)
* [with space wrapped](</assets/file with space.pdf>)

- These shouldn't be render correctly. (thus unable to open)
    * [with space raw](assets/file with space.pdf)
    * [with space raw](./assets/file with space.pdf)
    * [with space raw](/assets/file with space.pdf)

## Assets with wikilinks

This should open in the default OS app: [[assets/dummy-pdf.pdf]]

This should open inside VSCode: [[other-files/config.ts]]

## Regular navigation should still work
* Quick check navigate to this: [[sail://assets/note-in-asset-vault]]
* Fuller check go to [[sail.ref.links]]

## Images:
Refer to [[sail.ref.image]]
