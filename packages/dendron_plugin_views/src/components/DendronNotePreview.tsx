import React from "react";
import {
  DMessageSource,
  FOOTNOTE_DEF_CLASS,
  FOOTNOTE_REF_CLASS,
  NoteViewMessageEnum,
} from "@saili/common-all";
import { createLogger } from "../utils/logger";
import { DendronNote } from "./DendronNote";
import { useCurrentTheme, useMermaid, useRenderedNoteBody } from "../hooks";
import { DendronProps, DendronComponent } from "../types";

const DendronNotePreview: DendronComponent = (props: DendronProps)=>{
  const ctx = "DendronNotePreview";
  const logger = createLogger("DendronNotePreview");
  const noteProps = props.ide.noteActive;
  const [noteRenderedBody] = useRenderedNoteBody({
    ...props,
    noteProps,
    previewHTML: props.ide.previewHTML,
  });
  if (!noteRenderedBody) {
    // return <div>Loading...</div>;
    return <>
    <h1 id="test-note">Test Note</h1>
      <h1 id="header">Header</h1>
      <p> some content </p>
      <h2 id="subheader">Subheader</h2></>
  }
  return <>
    <DendronNote noteContent={noteRenderedBody} />
  </>
}

export default DendronNotePreview;