import { SailError, ERROR_STATUS, } from "@saili/common-all";
import { Router } from "express";
import asyncHandler from "express-async-handler";
import { WorkspaceController } from "../modules/workspace";
const router = Router();
router.post("/initialize", asyncHandler(async (req, res) => {
    const resp = await WorkspaceController.instance().init(req.body);
    res.json(resp);
}));
/**
 * Poll engine init status during fast-first startup. Returns
 * `{ state: "cold" | "warm" | "ready", progress? }`.
 */
router.get("/initStatus", asyncHandler(async (req, res) => {
    const ws = req.query.ws;
    const resp = await WorkspaceController.instance().initStatus({ ws });
    res.json(resp);
}));
router.post("/sync", asyncHandler(async (req, res) => {
    try {
        const resp = await WorkspaceController.instance().sync(req.body);
        res.json(resp);
    }
    catch (err) {
        res.json({
            error: new SailError({
                message: ERROR_STATUS.ENGINE_NOT_SET,
                payload: err,
            }),
        });
    }
}));
export { router as workspaceRouter };
//# sourceMappingURL=workspace.js.map