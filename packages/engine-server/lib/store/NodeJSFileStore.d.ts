import { GetAllFilesOpts, IFileStore, RespV3, URI } from "@saili/common-all";
export declare class NodeJSFileStore implements IFileStore {
    /**
     * See {@link IFileStore.read}
     */
    read(uri: URI): Promise<RespV3<string>>;
    /**
     * See {@link IFileStore.readDir}
     */
    readDir(opts: GetAllFilesOpts): Promise<RespV3<string[]>>;
    /**
     * See {@link IFileStore.write}
     */
    write(uri: URI, content: string): Promise<RespV3<URI>>;
    /**
     * See {@link IFileStore.delete}
     */
    delete(uri: URI): Promise<RespV3<URI>>;
    /**
     * See {@link IFileStore.rename}
     */
    rename(oldUri: URI, newUri: URI): Promise<RespV3<URI>>;
}
