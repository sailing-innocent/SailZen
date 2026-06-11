import {
  MetadataService,
  WorkspaceActivationContext,
} from "@saili/engine-server";
import { BlankInitializer } from "./blankInitializer";
import { TutorialInitializer } from "./tutorialInitializer";
import { WorkspaceInitializer } from "./workspaceInitializer";

/**
 * Factory class for creating WorkspaceInitializer types
 */
export class WorkspaceInitFactory {
  static create(): WorkspaceInitializer | undefined {
    switch (MetadataService.instance().getActivationContext()) {
      case WorkspaceActivationContext.tutorial:
        return new TutorialInitializer();

      default:
        return new BlankInitializer();
    }
  }
}
