---
id: PcnVj4GZBt7O3HTrwqdFz
title: ACM Test Paper for External Template
desc: "Test note for external acmart-sigconf LaTeX template pipeline"
updated: 1776609216113
created: 1714300000000
doc:
  role: standalone
  project: project.testdoc
  exports:
    - format: latex
      template: acmart-sigconf
  meta:
    authors:
      - name: Alice Example
        affiliation: SailZen Lab
        country: USA
        email: alice@example.com
      - name: Bob Demo
        affiliation: Example University
        country: USA
        email: bob@example.edu
    keywords:
      - markdown
      - latex
      - external-template
    conference:
      short: SIGCONF '26
      name: ACM SIGCONF 2026
      date: June 15--20, 2026
      venue: San Francisco, CA, USA
    year: "2026"
    doi: 10.1145/1234567.1234568
---

# Abstract

This paper demonstrates the SailZen Doc Engine external template pipeline using the acmart-sigconf template.

![[project.testdoc.content.intro]]

![[project.testdoc.content.method]]

# Conclusion

The external template mechanism successfully assembles ACM-style conference papers from structured notes ::cite[foo, bar].
