/**
 * Production entry point for sail_plugin_views
 * This file is the main entry for Vite build
 */
import { renderOnDOM } from "./bootstrap";
import "./styles/scss/main-plugin.scss";

// Static imports for components (Vite ESM doesn't support require())
import SailNotePreview from "./components/SailNotePreview";
import SailCalendarPanel from "./components/SailCalendarPanel";
import { SailComponent } from "./types";

// Component registry
const COMPONENTS: Record<string, SailComponent> = {
  SailNotePreview,
  SailCalendarPanel,
};

const VALID_NAMES = Object.keys(COMPONENTS);

const elem = window.document.getElementById("root")!;
const VIEW_NAME = elem.getAttribute("data-name")!;

if (VALID_NAMES.includes(VIEW_NAME)) {
  console.log("NAME VALID: ", VIEW_NAME);
  const View = COMPONENTS[VIEW_NAME];
  let props = {
    padding: "inherit",
  };
  if (VIEW_NAME === "SailNotePreview") {
    props = { padding: "33px" };
  }
  renderOnDOM(View, props);
} else {
  console.log(
    `${VIEW_NAME} is an invalid or empty name. please use one of the following: ${VALID_NAMES.join(
      " "
    )}`
  );
}
