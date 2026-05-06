import React from "react";
import {
  DMessageSource,
  NoteViewMessageEnum,
} from "@saili/common-all";
import { createLogger } from "../utils/logger";
import { DendronNote } from "./DendronNote";
import { useRenderedNoteBody } from "../hooks";
import { DendronProps, DendronComponent } from "../types";
import { postVSCodeMessage } from "../utils/vscode";

const DendronNotePreview: DendronComponent = (props: DendronProps)=>{
  const ctx = "DendronNotePreview";
  const logger = createLogger("DendronNotePreview");
  const noteProps = props.ide.noteActive;
  const [noteRenderedBody] = useRenderedNoteBody({
    ...props,
    noteProps,
    previewHTML: props.ide.previewHTML,
  });

  logger.info({ ctx, msg: "render", noteId: noteProps?.id, hasBody: !!noteRenderedBody });

  // 组件挂载时，如果没有活跃 note，主动向 VSCode 请求当前活跃编辑器
  React.useEffect(() => {
    if (!noteProps) {
      logger.info({ ctx, msg: "no noteActive on mount, requesting active editor" });
      postVSCodeMessage({
        type: NoteViewMessageEnum.onGetActiveEditor,
        data: {},
        source: DMessageSource.webClient,
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!noteProps) {
    // 没有活跃 note，显示空状态
    return <div style={{ padding: "1em", color: "var(--vscode-descriptionForeground)" }}>
      <p>No note selected. Open a Dendron note to preview it here.</p>
    </div>;
  }

  if (!noteRenderedBody) {
    // 有 note 但还在渲染中，显示 loading
    return <div style={{ padding: "1em", color: "var(--vscode-descriptionForeground)" }}>
      <p>Loading preview...</p>
    </div>;
  }

  return <>
    <DendronNote noteContent={noteRenderedBody} />
  </>
}

export default DendronNotePreview;
