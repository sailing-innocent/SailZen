import { renderOnDOM } from "./bootstrap";
import "./styles/scss/main-plugin.scss";
// import "./index.css";

const VALID_NAMES = [
  "DendronCalendarPanel",
  "DendronNotePreview"
];

const elem = window.document.getElementById("root")!;
const VIEW_NAME = elem.getAttribute("data-name")!;

if (VALID_NAMES.includes(VIEW_NAME)) {
  console.log("NAME VALID: ", VIEW_NAME);
  const View = require(`./components/${VIEW_NAME}`).default;
  let props = {
    padding: "inherit",
  };
  if (VIEW_NAME === "DendronNotePreview") {
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
