import { RespV2, RespV3, RespWithOptError } from "@saili/common-all";
import { Response } from "express";
export declare class ExpressUtils {
    /**
     * Utility to handle errors from Express
     * @param expressResponse : Response object form express
     * @param sailResponse : Response from Sail
     * @returns True if error was handled, false if no error
     */
    static handleError(expressResponse: Response, sailResponse: RespV2<any>): boolean;
    /**
     * Set a standard response format to express rest clients based on RespV2
     * @param expressResponse
     * @param sailResponse
     */
    static setResponse(expressResponse: Response, sailResponse: RespV3<any> | RespWithOptError<any>): void;
}
