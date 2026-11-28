import { DEngine } from "@saili/common-all";
export declare class MemoryStore {
    static _instance: MemoryStore;
    static instance(force?: boolean): MemoryStore;
    static store: () => any;
    put(key: string, value: any): Promise<void>;
    getEngine(): DEngine;
    get<T>(key: string): Promise<T | undefined>;
    list(prefix: string): Promise<any>;
}
