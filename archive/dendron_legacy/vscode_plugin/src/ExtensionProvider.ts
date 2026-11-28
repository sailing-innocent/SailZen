import { SailError } from "@saili/common-all";
import { ensureDirSync } from "fs-extra";
import _ from "lodash";
import { ISailExtension } from "./sailExtensionInterface";
import { IWSUtils } from "./WSUtilsInterface";

/**
 * Use this to statically get implementation of ISailExtension without having to
 * depend on concrete SailExtension.
 *
 * Note: Prefer to get ISailExtension injected into your classes upon their
 * construction rather than statically getting it from here. But if that's not
 * a fitting option then use this class.
 * */
export class ExtensionProvider {
  private static extension: ISailExtension;

  static getExtension(): ISailExtension {
    if (_.isUndefined(ExtensionProvider.extension)) {
      throw new SailError({
        message: `Extension is not yet registered. Make sure initialization registers extension prior to usage.`,
      });
    }

    return ExtensionProvider.extension;
  }

  static getCommentThreadsState() {
    return ExtensionProvider.extension.getCommentThreadsState();
  }

  static getDWorkspace() {
    return ExtensionProvider.getExtension().getDWorkspace();
  }

  static getEngine() {
    return ExtensionProvider.getExtension().getEngine();
  }

  static getWSUtils(): IWSUtils {
    return ExtensionProvider.getExtension().wsUtils;
  }

  static isActive() {
    return ExtensionProvider.getExtension().isActive();
  }

  static isActiveAndIsSailNote(fpath: string) {
    return ExtensionProvider.getExtension().isActiveAndIsSailNote(fpath);
  }

  static getWorkspaceConfig() {
    return ExtensionProvider.getExtension().getWorkspaceConfig();
  }

  static register(extension: ISailExtension) {
    ExtensionProvider.extension = extension;
  }
}

