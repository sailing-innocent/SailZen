import { ExpressUtils } from "@saili/common-server";
import { Router } from "express";
import asyncHandler from "express-async-handler";
import { getLogger } from "../core";
import { ConfigController } from "../modules/config";
const router = Router();
const L = getLogger();
const ctx = "config";
router.get("/get", asyncHandler(async (req, res) => {
    L.info({ ctx, msg: "get:enter" });
    const resp = await ConfigController.instance().get(req.query);
    L.info({ ctx, msg: "get:ext", resp });
    ExpressUtils.setResponse(res, resp);
}));
export { router as configRouter };
//# sourceMappingURL=config.js.map