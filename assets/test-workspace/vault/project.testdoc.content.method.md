---
id: de5a4f27-4c47-4982-b8fb-e5265aea0c63
title: Methodology
desc: "Compose note: methodology section"
updated: 1714300000000
created: 1714300000000
doc:
  role: compose
  project: project.testdoc
  order: 2
---

# Methodology

This section describes the methodology. It contains nested references and multiple citations.

## Design

Our design follows a pipeline architecture ::cite[bar].

```python
def assemble(profile, notes):
    body = expand_refs(profile.root, notes)
    for note in profile.discovered:
        body += "\n\n" + expand_refs(note, notes)
    return body
```

## Implementation

The implementation uses recursive expansion for note references.

$$E = mc^2$$

This is a block math equation that should be preserved in LaTeX.
