export const isDisposable = (cmd) => {
    return cmd.dispose !== undefined;
};
/** Mirrors VSCode's `DiagnosticSeverity` */
export var DiagnosticSeverity;
(function (DiagnosticSeverity) {
    DiagnosticSeverity[DiagnosticSeverity["Error"] = 0] = "Error";
    DiagnosticSeverity[DiagnosticSeverity["Warning"] = 1] = "Warning";
    DiagnosticSeverity[DiagnosticSeverity["Information"] = 2] = "Information";
    DiagnosticSeverity[DiagnosticSeverity["Hint"] = 3] = "Hint";
})(DiagnosticSeverity || (DiagnosticSeverity = {}));
//# sourceMappingURL=compat.js.map