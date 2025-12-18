/**
 * @file Zotero.ts
 * @brief The Dendron Zotero Command
 * @author sailing-innocent
 * @date 2025-06-03
 */

import requestPromise from 'request-promise';
import * as vscode from 'vscode';
import { Logger } from '../logger';

export async function showZoteroPicker(): Promise<void> {
  try {
    // const url = "http://127.0.0.1:23119/better-bibtex/cayw?format=pandoc"
    const url = "http://127.0.0.1:23119/better-bibtex/cayw?format=translate&translator=csljson"
    const result: any = await requestPromise(String(url));
    // json parse result


    if (result) {
      const parsedResult = JSON.parse(result);
      console.log('Zotero citation fetched:', parsedResult);
      console.log('Zotero citation fetched:', parsedResult[0]);
      Logger.info(`Zotero citation fetched [LOG_INFO]: ${result}`);

      // Uncomment if you want to insert the ID into the active editor

      const editor = vscode.window.activeTextEditor;
      if (editor) {
          editor.edit(editBuilder => {
            editor.selections.forEach(selection => {
              editBuilder.delete(selection);
              if (parsedResult.length == 1) {
                editBuilder.insert(selection.start, `${parsedResult[0].title} \\cite{${parsedResult[0].id}}`);
              }
              else{
                parsedResult.forEach((item: any) => {
                  editBuilder.insert(selection.start, `- ${item.title} \\cite{${item.id}}\n`);
                })
              }
            });
          });
      }
    }
  } catch (err: any) {
    console.log('Failed to fetch citation: %j', err.message);
    vscode.window.showErrorMessage('Zotero Citations: could not connect to Zotero. Are you sure it is running?');
  }
}

async function openInZotero(): Promise<void> {
  const editor = vscode.window.activeTextEditor;

  if (!editor) {
    return;
  }

  let citeKey: string = '';

  if (editor.selection.isEmpty) {
    const range = editor.document.getWordRangeAtPosition(editor.selection.active);
    if (range) {
      citeKey = editor.document.getText(range);
    }
  } else {
    citeKey = editor.document.getText(new vscode.Range(editor.selection.start, editor.selection.end));
  }

  console.log(`Opening ${citeKey} in Zotero`);
  const uri = vscode.Uri.parse(`zotero://select/items/bbt:${citeKey}`);
  await vscode.env.openExternal(uri);
}

async function openPDFZotero(): Promise<void> {
  const editor = vscode.window.activeTextEditor;

  if (!editor) {
    return;
  }

  let citeKey: string = '';

  if (editor.selection.isEmpty) {
    const range = editor.document.getWordRangeAtPosition(editor.selection.active);
    if (range) {
      citeKey = editor.document.getText(range);
    }
  } else {
    citeKey = editor.document.getText(new vscode.Range(editor.selection.start, editor.selection.end));
  }

  console.log(`Opening ${citeKey} in Zotero`);

  const options = {
    method: 'POST',
    uri: 'http://localhost:23119/better-bibtex/json-rpc',
    body: {
      'jsonrpc': '2.0',
      'method': 'item.attachments',
      'params': [citeKey]
    },
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'User-Agent': 'Request-Promise'
    },
    json: true // Automatically parses the JSON string in the response
  };

  let uri = vscode.Uri.parse(`zotero://select/items/bbt:${citeKey}`);

  try {
    const repos: any = await requestPromise(options);
    console.log(repos['result']);
    console.log('User has %d repos', repos['result'].length);
    for (const elt of repos['result']) {
      if (elt['path'].endsWith('.pdf')) {
        uri = vscode.Uri.parse(elt['open']);
        break;
      }
    }
    console.log(uri);
    await vscode.env.openExternal(uri);
  } catch (err: any) {
    console.log('API open PDF in Zotero failed', err);
  }
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(vscode.commands.registerCommand('dendron.zotero.openInZotero', openInZotero));
  context.subscriptions.push(vscode.commands.registerCommand('dendron.zotero.openPDFZotero', openPDFZotero));

  let disposable = vscode.commands.registerCommand('dendron.zotero.CitationPicker', () => {
    showZoteroPicker();
  });

  context.subscriptions.push(disposable);
}

export function deactivate(): void {
  // This function is called when the extension is deactivated
}
