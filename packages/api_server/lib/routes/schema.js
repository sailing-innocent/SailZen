import { Router } from "express";
import asyncHandler from "express-async-handler";
import { SchemaController } from "../modules/schemas";
const router = Router();
router.get("/get", asyncHandler(async (req, res) => {
    const resp = await SchemaController.instance().get(req.query);
    res.json(resp);
}));
router.post("/delete", asyncHandler(async (req, res) => {
    const resp = await SchemaController.instance().delete(req.body);
    res.json(resp);
}));
router.post("/query", asyncHandler(async (req, res) => {
    const resp = await SchemaController.instance().query(req.body);
    res.json(resp);
}));
router.post("/write", asyncHandler(async (req, res) => {
    const resp = await SchemaController.instance().create(req.body);
    res.json(resp);
}));
export { router as schemaRouter };
//# sourceMappingURL=schema.js.map