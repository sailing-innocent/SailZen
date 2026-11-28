import { CodeCommandConstructor } from "./base";
import { AddAndCommit } from "./AddAndCommit";
import { ApplyTemplateCommand } from "./ApplyTemplateCommand";
import { ArchiveHierarchyCommand } from "./ArchiveHierarchy";
import { BrowseNoteCommand } from "./BrowseNoteCommand";
import { ChangeWorkspaceCommand } from "./ChangeWorkspace";
import { ConfigureCommand } from "./ConfigureCommand";
import { ConfigureLocalOverride } from "./ConfigureLocalOverride";
import { ConfigureGraphStylesCommand } from "./ConfigureGraphStyles";
import { ConfigureNoteTraitsCommand } from "./ConfigureNoteTraitsCommand";

import { ConvertCandidateLinkCommand } from "./ConvertCandidateLink";
import { ConvertLinkCommand } from "./ConvertLink";
import { CopyNoteLinkCommand } from "./CopyNoteLink";
import { CopyNoteRefCommand } from "./CopyNoteRef";
import { CopyNoteURLCommand } from "./CopyNoteURL";
import { CopyToClipboardCommand } from "./CopyToClipboardCommand";
import { CreateDailyJournalCommand } from "./CreateDailyJournal";
import { CreateHookCommand } from "./CreateHookCommand";
import { CreateJournalNoteCommand } from "./CreateJournalNoteCommand";
import { CreateMeetingNoteCommand } from "./CreateMeetingNoteCommand";
import { CreateNoteWithUserDefinedTrait } from "./CreateNoteWithUserDefinedTrait";
import { CreateSchemaFromHierarchyCommand } from "./CreateSchemaFromHierarchyCommand";
import { CreateScratchNoteCommand } from "./CreateScratchNoteCommand";
import { CreateTaskCommand } from "./CreateTask";
import { DeleteHookCommand } from "./DeleteHookCommand";
import { DeleteCommand } from "./DeleteCommand";
import { DevTriggerCommand } from "./DevTriggerCommand";
import { DiagnosticsReportCommand } from "./DiagnosticsReport";
import { DoctorCommand } from "./Doctor";
import { GoDownCommand } from "./GoDownCommand";
import { GotoCommand } from "./Goto";
import { GotoNoteCommand } from "./GotoNote";
import { GoUpCommand } from "./GoUpCommand";
import { InsertNoteIndexCommand } from "./InsertNoteIndexCommand";
import { InsertNoteLinkCommand } from "./InsertNoteLink";
import { MoveHeaderCommand } from "./MoveHeader";
import { MoveNoteCommand } from "./MoveNoteCommand";
import { NoteLookupAutoCompleteCommand } from "./node/NoteLookupAutoCompleteCommand";
import { NoteLookupCommand } from "./NoteLookupCommand";
import { OpenBackupCommand } from "./OpenBackupCommand";
import { OpenLinkCommand } from "./OpenLink";
import { OpenLogsCommand } from "./OpenLogs";
import { PasteFileCommand } from "./PasteFile";
import { PasteLinkCommand } from "./PasteLink";
import { RandomNoteCommand } from "./RandomNote";
import { RefactorHierarchyCommand } from "./RefactorHierarchy";
import { RegisterNoteTraitCommand } from "./RegisterNoteTraitCommand";
import { RenameHeaderCommand } from "./RenameHeader";
import { ResetConfigCommand } from "./ResetConfig";
import { SchemaLookupCommand } from "./SchemaLookupCommand";
import { SetupWorkspaceCommand } from "./SetupWorkspace";
import { ShowHelpCommand } from "./ShowHelp";
import { SyncCommand } from "./Sync";
import { TaskCompleteCommand } from "./TaskComplete";
import { TaskStatusCommand } from "./TaskStatus";
import { UpgradeSettingsCommand } from "./UpgradeSettings";
import { ValidateEngineCommand } from "./ValidateEngineCommand";
import { VaultAddCommand } from "./VaultAddCommand";
import { ConvertVaultCommand } from "./ConvertVaultCommand";
import { BatchRenameNoteCommand } from "./BatchRenameNoteCommand";
import { RenameNoteCommand } from "./RenameNoteCommand";
import { CreateNoteCommand } from "./CreateNoteCommand";
import { MergeNoteCommand } from "./MergeNoteCommand";
import { MoveSelectionToCommand } from "./MoveSelectionToCommand";
import { RemoveVaultCommand } from "./RemoveVaultCommand";
import { CreateNewVaultCommand } from "./CreateNewVaultCommand";
import { AddExistingVaultCommand } from "./AddExistingVaultCommand";
import { ExportNoteCommand } from "./ExportNoteCommand";
import { CompileDocumentCommand } from "./CompileDocumentCommand";

/**
 * Note: this does not contain commands that have parametered constructors, as
 * those cannot be cast to the CodeCommandConstructor interface.
 */
const ALL_COMMANDS = [
  AddAndCommit,
  ArchiveHierarchyCommand,
  BrowseNoteCommand,
  ChangeWorkspaceCommand,
  ConfigureCommand,
  ConfigureLocalOverride,
  ConfigureGraphStylesCommand,
  CopyNoteLinkCommand,
  CopyNoteRefCommand,
  CopyNoteURLCommand,
  CopyToClipboardCommand,
  CreateDailyJournalCommand,
  CreateHookCommand,
  CreateSchemaFromHierarchyCommand,
  DeleteHookCommand,
  DeleteCommand,
  DiagnosticsReportCommand,
  DevTriggerCommand,
  DoctorCommand,
  GoDownCommand,
  GoUpCommand,
  GotoCommand,
  GotoNoteCommand,
  InsertNoteLinkCommand,
  InsertNoteIndexCommand,
  NoteLookupCommand,
  NoteLookupAutoCompleteCommand,
  CreateJournalNoteCommand,
  CreateScratchNoteCommand,
  CreateMeetingNoteCommand,
  SchemaLookupCommand,
  OpenLinkCommand,
  OpenLogsCommand,
  PasteFileCommand,
  PasteLinkCommand,
  MoveNoteCommand,
  MoveSelectionToCommand,
  RenameNoteCommand,
  BatchRenameNoteCommand,
  RenameHeaderCommand,
  MoveHeaderCommand,
  RefactorHierarchyCommand,
  RandomNoteCommand,
  ResetConfigCommand,
  SetupWorkspaceCommand,
  ShowHelpCommand,
  SyncCommand,
  ApplyTemplateCommand,
  UpgradeSettingsCommand,
  VaultAddCommand,
  CreateNewVaultCommand,
  AddExistingVaultCommand,
  RemoveVaultCommand,
  ConvertVaultCommand,
  ConvertLinkCommand,
  ConvertCandidateLinkCommand,
  CreateTaskCommand,
  TaskStatusCommand,
  TaskCompleteCommand,
  RegisterNoteTraitCommand,
  ConfigureNoteTraitsCommand,
  CreateNoteWithUserDefinedTrait,
  OpenBackupCommand,
  ValidateEngineCommand,
  MergeNoteCommand,
  CreateNoteCommand,
  ExportNoteCommand,
  CompileDocumentCommand,
] as CodeCommandConstructor[];

export { ALL_COMMANDS };

