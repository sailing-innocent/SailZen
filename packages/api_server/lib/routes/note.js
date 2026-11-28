import { ExpressUtils } from "@saili/common-server";
import { Router } from "express";
import asyncHandler from "express-async-handler";
import { NoteController } from "../modules/notes";
import { getWSEngine } from "../utils";
const router = Router();
router.get("/get", asyncHandler(async (req, res) => {
    const { id, ws } = req.query;
    const engine = await getWSEngine({ ws: ws || "" });
    ExpressUtils.setResponse(res, await engine.getNote(id));
}));
router.get("/getMeta", asyncHandler(async (req, res) => {
    const { id, ws } = req.query;
    const engine = await getWSEngine({ ws: ws || "" });
    ExpressUtils.setResponse(res, await engine.getNoteMeta(id));
}));
router.get("/bulkGet", asyncHandler(async (req, res) => {
    const { ids, ws } = req.query;
    const engine = await getWSEngine({ ws: ws || "" });
    ExpressUtils.setResponse(res, await engine.bulkGetNotes(ids));
}));
router.get("/bulkGetMeta", asyncHandler(async (req, res) => {
    const { ids, ws } = req.query;
    const engine = await getWSEngine({ ws: ws || "" });
    ExpressUtils.setResponse(res, await engine.bulkGetNotesMeta(ids));
}));
router.post("/delete", asyncHandler(async (req, res) => {
    const { ws, id, opts } = req.body;
    const engine = await getWSEngine({ ws: ws || "" });
    ExpressUtils.setResponse(res, await engine.deleteNote(id, opts));
}));
router.get("/info", asyncHandler(async (_req, res) => {
    const resp = await NoteController.instance().info();
    res.json(resp);
}));
router.post("/rename", asyncHandler(async (req, res) => {
    const resp = await NoteController.instance().rename(req.body);
    ExpressUtils.setResponse(res, resp);
}));
router.post("/render", asyncHandler(async (req, res) => {
    const resp = await NoteController.instance().render(req.body);
    ExpressUtils.setResponse(res, resp);
}));
router.get("/query", asyncHandler(async (req, res) => {
    const resp = await NoteController.instance().query(req.query);
    ExpressUtils.setResponse(res, { data: resp });
}));
router.post("/find", asyncHandler(async (req, res) => {
    const { ws, ...opts } = req.body;
    const engine = await getWSEngine({ ws: ws || "" });
    const out = await engine.findNotes(opts);
    ExpressUtils.setResponse(res, { data: out });
}));
router.post("/findMeta", asyncHandler(async (req, res) => {
    const { ws, ...opts } = req.body;
    const engine = await getWSEngine({ ws: ws || "" });
    const out = await engine.findNotesMeta(opts);
    ExpressUtils.setResponse(res, { data: out });
}));
router.post("/write", asyncHandler(async (req, res) => {
    const { ws, node, opts } = req.body;
    const engine = await getWSEngine({ ws: ws || "" });
    const out = await engine.writeNote(node, opts);
    ExpressUtils.setResponse(res, out);
}));
router.post("/bulkAdd", asyncHandler(async (req, res) => {
    const { ws, opts } = req.body;
    const engine = await getWSEngine({ ws: ws || "" });
    const out = await engine.bulkWriteNotes(opts);
    ExpressUtils.setResponse(res, out);
}));
router.get("/blocks", asyncHandler(async (req, res) => {
    const { id, ws, filterByAnchorType } = req.query;
    const engine = await getWSEngine({ ws: ws || "" });
    ExpressUtils.setResponse(res, await engine.getNoteBlocks({ id, filterByAnchorType }));
}));
router.post("/decorations", asyncHandler(async (req, res) => {
    const opts = req.body;
    const { ws } = opts;
    const engine = await getWSEngine({ ws: ws || "" });
    ExpressUtils.setResponse(res, await engine.getDecorations(opts));
}));
export { router as noteRouter };
//# sourceMappingURL=note.js.map