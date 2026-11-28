export type DHookEntry = {
    id: string;
    pattern: string;
    type: "js";
};
export type DHookDict = {
    onCreate: DHookEntry[];
};
export declare enum DHookType {
    onCreate = "onCreate"
}
