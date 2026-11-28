export declare class AssertionError extends Error {
}
export declare function assertExists<T = any>(val: T, msg: string): NonNullable<T>;
export declare function assert(statement: boolean, msg: string): boolean;
