import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
	// Initialize Status bar
	// Initialize Tree provider
	// Initialize Online Tree Provider

	// Register commands
	context.subscriptions.push(
		// Workspace commands
		vscode.commands.registerCommand('sailzen.initVault', async () => {
			vscode.window.showInformationMessage("Hello InitVault");
		})
	)
}

export function deactivate() { }