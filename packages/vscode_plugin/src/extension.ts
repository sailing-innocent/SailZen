import * as vscode from 'vscode'

export function activate(context: vscode.ExtensionContext) {
    context.subscriptions.push(
        vscode.commands.registerCommand("sailzen.SayHello", async () => {
            vscode.window.showWarningMessage("SayHello");
        })
    )
}

export function deactivate() {

}