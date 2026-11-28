export declare function makeResponse<T>(resp: T): Promise<Awaited<T>>;
/**
 * Loop through iterable one element at a time and await on async callback at every iteration
 */
export declare function asyncLoopOneAtATime<T, R = any>(things: T[], cb: (t: T) => Promise<R>): Promise<R[]>;
/**
 * Loop through iterable in parallel
 * @param things
 * @param cb
 * @returns
 */
export declare function asyncLoop<T>(things: T[], cb: (t: T) => Promise<any>): Promise<any[]>;
