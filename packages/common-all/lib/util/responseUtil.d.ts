import { RespV2 } from "../types";
import { SailError } from "../error";
/** Utility for {@link RespV2} */
export declare class ResponseUtil {
    /** true when response has an error; false otherwise. */
    static hasError<T>(resp: RespV2<T>): boolean;
    static createHappyResponse<T>(input: {
        data: T;
    }): RespV2<T>;
    static createUnhappyResponse<T>(input: {
        error: SailError;
    }): RespV2<T>;
}
