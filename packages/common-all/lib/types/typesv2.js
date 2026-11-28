export var MergeConflictOptions;
(function (MergeConflictOptions) {
    MergeConflictOptions["OVERWRITE_LOCAL"] = "Overwrite local value with remote value";
    MergeConflictOptions["OVERWRITE_REMOTE"] = "Overwrite remote value with local value";
    MergeConflictOptions["SKIP"] = "Skip this conflict(We will not merge, you'll resolve this manually)";
    MergeConflictOptions["SKIP_ALL"] = "Skip All (you'll resolve all next conflicted entries manually) ";
})(MergeConflictOptions || (MergeConflictOptions = {}));
export var DMessageSource;
(function (DMessageSource) {
    DMessageSource["vscode"] = "vscode";
    DMessageSource["webClient"] = "webClient";
})(DMessageSource || (DMessageSource = {}));
export var DMessageEnum;
(function (DMessageEnum) {
    /**
     * View is ready
     */
    DMessageEnum["INIT"] = "init";
    DMessageEnum["ON_DID_CHANGE_ACTIVE_TEXT_EDITOR"] = "onDidChangeActiveTextEditor";
    DMessageEnum["ON_UPDATE_PREVIEW_HTML"] = "onUpdatePreviewHTML";
    DMessageEnum["MESSAGE_DISPATCHER_READY"] = "messageDispatcherReady";
})(DMessageEnum || (DMessageEnum = {}));
export var GraphViewMessageEnum;
(function (GraphViewMessageEnum) {
    GraphViewMessageEnum["onSelect"] = "onSelect";
    GraphViewMessageEnum["onGetActiveEditor"] = "onGetActiveEditor";
    GraphViewMessageEnum["onReady"] = "onReady";
    GraphViewMessageEnum["onRequestGraphOpts"] = "onRequestGraphOpts";
    GraphViewMessageEnum["onGraphLoad"] = "onGraphLoad";
    GraphViewMessageEnum["onGraphThemeChange"] = "onGraphThemeChange";
    GraphViewMessageEnum["configureCustomStyling"] = "configureCustomStyling";
    GraphViewMessageEnum["toggleGraphView"] = "toggleGraphView";
    GraphViewMessageEnum["onGraphDepthChange"] = "onGraphDepthChange";
    GraphViewMessageEnum["toggleGraphEdges"] = "toggleGraphEdges";
})(GraphViewMessageEnum || (GraphViewMessageEnum = {}));
export var CalendarViewMessageType;
(function (CalendarViewMessageType) {
    CalendarViewMessageType["onSelect"] = "onSelect";
    CalendarViewMessageType["onGetActiveEditor"] = "onGetActiveEditor";
    CalendarViewMessageType["messageDispatcherReady"] = "messageDispatcherReady";
})(CalendarViewMessageType || (CalendarViewMessageType = {}));
export var NoteViewMessageEnum;
(function (NoteViewMessageEnum) {
    NoteViewMessageEnum["onClick"] = "onClick";
    NoteViewMessageEnum["onGetActiveEditor"] = "onGetActiveEditor";
    NoteViewMessageEnum["onLock"] = "onLock";
    NoteViewMessageEnum["onUnlock"] = "onUnlock";
})(NoteViewMessageEnum || (NoteViewMessageEnum = {}));
export var LookupViewMessageEnum;
(function (LookupViewMessageEnum) {
    LookupViewMessageEnum["onUpdate"] = "onUpdate";
    LookupViewMessageEnum["onValuesChange"] = "onValuesChange";
    LookupViewMessageEnum["onRequestControllerState"] = "onRequestControllerState";
})(LookupViewMessageEnum || (LookupViewMessageEnum = {}));
export var ThemeMessageType;
(function (ThemeMessageType) {
    ThemeMessageType["onThemeChange"] = "onThemeChange";
    ThemeMessageType["getTheme"] = "getTheme";
})(ThemeMessageType || (ThemeMessageType = {}));
export var SeedBrowserMessageType;
(function (SeedBrowserMessageType) {
    SeedBrowserMessageType["onSeedAdd"] = "onSeedAdd";
    SeedBrowserMessageType["onOpenUrl"] = "onOpenUrl";
    SeedBrowserMessageType["onSeedStateChange"] = "onSeedStateChange";
})(SeedBrowserMessageType || (SeedBrowserMessageType = {}));
export var ConfigureUIMessageEnum;
(function (ConfigureUIMessageEnum) {
    ConfigureUIMessageEnum["onUpdateConfig"] = "onUpdateConfig";
    ConfigureUIMessageEnum["openSailConfigYaml"] = "openSailConfigYaml";
})(ConfigureUIMessageEnum || (ConfigureUIMessageEnum = {}));
export var GraphThemeEnum;
(function (GraphThemeEnum) {
    GraphThemeEnum["Block"] = "Block";
    GraphThemeEnum["Classic"] = "Classic";
    GraphThemeEnum["Monokai"] = "Monokai";
    GraphThemeEnum["Custom"] = "Custom";
})(GraphThemeEnum || (GraphThemeEnum = {}));
export var GraphTypeEnum;
(function (GraphTypeEnum) {
    GraphTypeEnum["fullGraph"] = "fullGraph";
    GraphTypeEnum["localGraph"] = "localGraph";
})(GraphTypeEnum || (GraphTypeEnum = {}));
//# sourceMappingURL=typesv2.js.map