import {
  ILookupProviderOpts,
  ILookupProvider,
  INoteLookupProviderFactory,
  ISchemaLookupProviderFactory,
} from "./LookupProviderInterface";
import { SchemaLookupProvider } from "./SchemaLookupProvider";
import { NoteLookupProvider } from "./NoteLookupProvider";
import { IDendronExtension } from "../../dendronExtensionInterface";

export class NoteLookupProviderFactory implements INoteLookupProviderFactory {
  private extension: IDendronExtension;

  constructor(extension: IDendronExtension) {
    this.extension = extension;
  }

  create(id: string, opts: ILookupProviderOpts) {
    return new NoteLookupProvider(id, opts, this.extension);
  }
}

export class SchemaLookupProviderFactory
  implements ISchemaLookupProviderFactory
{
  private extension: IDendronExtension;

  constructor(extension: IDendronExtension) {
    this.extension = extension;
  }

  create(id: string, opts: ILookupProviderOpts): ILookupProvider {
    return new SchemaLookupProvider(id, opts, this.extension);
  }
}

