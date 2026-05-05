/**
 * @file templateLoader.test.ts
 * @brief Unit tests for external template discovery and loading
 */

import fs from "fs-extra";
import path from "path";
import os from "os";
import {
  loadExternalTemplate,
  resolveTemplateDir,
  listExternalTemplates,
  renderSkeleton,
  renderExternalTemplate,
} from "../templateLoader";

describe("templateLoader", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "sz-template-test-"));
  });

  afterEach(async () => {
    await fs.remove(tmpDir);
  });

  // ========================================================================
  // resolveTemplateDir
  // ========================================================================

  describe("resolveTemplateDir", () => {
    it("should find template in .templates/<format>/<id>/", async () => {
      const tplDir = path.join(tmpDir, ".templates", "latex", "mytpl");
      await fs.ensureDir(tplDir);
      const result = await resolveTemplateDir("mytpl", "latex", tmpDir);
      expect(result).toBe(tplDir);
    });

    it("should find template in doc/template/<id>/", async () => {
      const tplDir = path.join(tmpDir, "doc", "template", "mytpl");
      await fs.ensureDir(tplDir);
      const result = await resolveTemplateDir("mytpl", "latex", tmpDir);
      expect(result).toBe(tplDir);
    });

    it("should prefer .templates over doc/template", async () => {
      const overrideDir = path.join(tmpDir, ".templates", "latex", "mytpl");
      const fallbackDir = path.join(tmpDir, "doc", "template", "mytpl");
      await fs.ensureDir(overrideDir);
      await fs.ensureDir(fallbackDir);
      const result = await resolveTemplateDir("mytpl", "latex", tmpDir);
      expect(result).toBe(overrideDir);
    });

    it("should return undefined when template does not exist", async () => {
      const result = await resolveTemplateDir("missing", "latex", tmpDir);
      expect(result).toBeUndefined();
    });
  });

  // ========================================================================
  // loadExternalTemplate
  // ========================================================================

  describe("loadExternalTemplate", () => {
    it("should parse template.yml and return ExternalTemplate", async () => {
      const tplDir = path.join(tmpDir, "acmart-sigconf");
      await fs.ensureDir(tplDir);
      await fs.writeFile(
        path.join(tplDir, "template.yml"),
        `id: acmart-sigconf
format: latex
description: ACM Conference Paper
engine: pdflatex
requires:
  - acmart.cls
variables:
  - name: title
    required: true
sectioning:
  style: numbered
  maxDepth: 3
`
      );
      await fs.writeFile(path.join(tplDir, "acmart.cls"), "% dummy cls");

      const ext = await loadExternalTemplate(tplDir);
      expect(ext).toBeDefined();
      expect(ext!.id).toBe("acmart-sigconf");
      expect(ext!.format).toBe("latex");
      expect(ext!.engine).toBe("pdflatex");
      expect(ext!.requires).toEqual(["acmart.cls"]);
      expect(ext!.resolvedRequires).toHaveLength(1);
      expect(ext!.resolvedRequires[0].fileName).toBe("acmart.cls");
      expect(ext!.mainTemplatePath).toBeUndefined();
    });

    it("should fallback to template.json when template.yml is absent", async () => {
      const tplDir = path.join(tmpDir, "article");
      await fs.ensureDir(tplDir);
      await fs.writeFile(
        path.join(tplDir, "template.json"),
        JSON.stringify({
          id: "article",
          format: "latex",
          description: "Basic Article",
          engine: "xelatex",
        })
      );

      const ext = await loadExternalTemplate(tplDir);
      expect(ext).toBeDefined();
      expect(ext!.id).toBe("article");
    });

    it("should detect main.tex skeleton when present", async () => {
      const tplDir = path.join(tmpDir, "article");
      await fs.ensureDir(tplDir);
      await fs.writeFile(
        path.join(tplDir, "template.yml"),
        "id: article\nformat: latex\ndescription: Article\n"
      );
      await fs.writeFile(path.join(tplDir, "main.tex"), "% skeleton");

      const ext = await loadExternalTemplate(tplDir);
      expect(ext!.mainTemplatePath).toBe(path.join(tplDir, "main.tex"));
    });

    it("should return undefined when no metadata file exists", async () => {
      const tplDir = path.join(tmpDir, "empty");
      await fs.ensureDir(tplDir);
      const ext = await loadExternalTemplate(tplDir);
      expect(ext).toBeUndefined();
    });

    it("should skip missing requires files", async () => {
      const tplDir = path.join(tmpDir, "missing-deps");
      await fs.ensureDir(tplDir);
      await fs.writeFile(
        path.join(tplDir, "template.yml"),
        "id: missing-deps\nformat: latex\nrequires:\n  - missing.cls\n"
      );

      const ext = await loadExternalTemplate(tplDir);
      expect(ext!.resolvedRequires).toHaveLength(0);
    });
  });

  // ========================================================================
  // listExternalTemplates
  // ========================================================================

  describe("listExternalTemplates", () => {
    it("should list templates from both search directories", async () => {
      const tpl1 = path.join(tmpDir, ".templates", "latex", "tpl-a");
      const tpl2 = path.join(tmpDir, "doc", "template", "tpl-b");
      await fs.ensureDir(tpl1);
      await fs.ensureDir(tpl2);
      await fs.writeFile(
        path.join(tpl1, "template.yml"),
        "id: tpl-a\nformat: latex\ndescription: A\n"
      );
      await fs.writeFile(
        path.join(tpl2, "template.yml"),
        "id: tpl-b\nformat: latex\ndescription: B\n"
      );

      const list = await listExternalTemplates("latex", tmpDir);
      expect(list).toHaveLength(2);
      expect(list.map((t) => t.id)).toContain("tpl-a");
      expect(list.map((t) => t.id)).toContain("tpl-b");
    });

    it("should deduplicate by id, preferring .templates", async () => {
      const tpl1 = path.join(tmpDir, ".templates", "latex", "dup");
      const tpl2 = path.join(tmpDir, "doc", "template", "dup");
      await fs.ensureDir(tpl1);
      await fs.ensureDir(tpl2);
      await fs.writeFile(
        path.join(tpl1, "template.yml"),
        "id: dup\nformat: latex\ndescription: From .templates\n"
      );
      await fs.writeFile(
        path.join(tpl2, "template.yml"),
        "id: dup\nformat: latex\ndescription: From doc/template\n"
      );

      const list = await listExternalTemplates("latex", tmpDir);
      expect(list).toHaveLength(1);
      expect(list[0].description).toBe("From .templates");
    });

    it("should skip templates with mismatched format", async () => {
      const tplDir = path.join(tmpDir, "doc", "template", "typst-tpl");
      await fs.ensureDir(tplDir);
      await fs.writeFile(
        path.join(tplDir, "template.yml"),
        "id: typst-tpl\nformat: typst\ndescription: Typst\n"
      );

      const list = await listExternalTemplates("latex", tmpDir);
      expect(list).toHaveLength(0);
    });
  });

  // ========================================================================
  // renderSkeleton
  // ========================================================================

  describe("renderSkeleton", () => {
    it("should substitute {{variable}} placeholders", () => {
      const skeleton = "\\title{{{title}}}\\author{{{author}}}";
      const result = renderSkeleton(skeleton, {
        title: "My Paper",
        author: "Alice",
      });
      expect(result).toBe("\\title{My Paper}\\author{Alice}");
    });

    it("should render {{#if}} blocks conditionally", () => {
      const skeleton =
        "{{#if abstract}}\\begin{abstract}\n{{abstract}}\n\\end{abstract}{{/if}}";
      const withAbstract = renderSkeleton(skeleton, {
        abstract: "It works!",
      });
      expect(withAbstract).toContain("\\begin{abstract}");
      expect(withAbstract).toContain("It works!");

      const withoutAbstract = renderSkeleton(skeleton, {});
      expect(withoutAbstract).toBe("");
    });

    it("should render {{#each}} blocks for arrays", () => {
      const skeleton = "{{#each authors}}\\author{{{name}}}{{/each}}";
      const result = renderSkeleton(skeleton, {
        authors: [{ name: "Alice" }, { name: "Bob" }],
      });
      expect(result).toBe("\\author{Alice}\n\\author{Bob}");
    });

    it("should substitute arrays as newline-joined strings", () => {
      const skeleton = "{{keywords}}";
      const result = renderSkeleton(skeleton, { keywords: ["a", "b", "c"] });
      expect(result).toBe("a\nb\nc");
    });

    it("should leave unknown variables empty", () => {
      const skeleton = "\\title{{{title}}}";
      const result = renderSkeleton(skeleton, {});
      expect(result).toBe("\\title{}");
    });
  });

  // ========================================================================
  // renderExternalTemplate
  // ========================================================================

  describe("renderExternalTemplate", () => {
    it("should render main.tex skeleton with pre-formatted helpers", async () => {
      const tplDir = path.join(tmpDir, "article");
      await fs.ensureDir(tplDir);
      await fs.writeFile(
        path.join(tplDir, "template.yml"),
        "id: article\nformat: latex\n"
      );
      await fs.writeFile(
        path.join(tplDir, "main.tex"),
        `\\documentclass{article}
\\title{{{title}}}
{{authors_latex}}
\\begin{document}
\\maketitle
{{body}}
\\end{document}
`
      );

      const ext = (await loadExternalTemplate(tplDir))!;
      const rendered = await renderExternalTemplate(
        ext,
        {
          title: "Test",
          authors: [{ name: "Alice" }],
        },
        "\\section{Hello}"
      );
      expect(rendered.mainContent).toContain("\\title{Test}");
      expect(rendered.mainContent).toContain("\\author{Alice}");
      expect(rendered.mainContent).toContain("\\section{Hello}");
    });

    it("should throw when no main.tex skeleton exists", async () => {
      const tplDir = path.join(tmpDir, "bare");
      await fs.ensureDir(tplDir);
      await fs.writeFile(
        path.join(tplDir, "template.yml"),
        "id: bare\nformat: latex\n"
      );

      const ext = (await loadExternalTemplate(tplDir))!;
      await expect(
        renderExternalTemplate(ext, {}, "body")
      ).rejects.toThrow(/no main.tex skeleton/);
    });
  });
});
